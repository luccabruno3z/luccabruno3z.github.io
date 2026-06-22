"""Daily-partitioned, append-only storage for parsed demo rounds.

Replaces the old monolithic ``graphs/demos/round_history.json`` (which grew
without bound and hit GitHub's 100 MB per-file push limit, bloating git
history by tens of GB because the whole file was re-committed every run).

Layout::

    graphs/demos/rounds/
        2026-03-17.json   ← rounds whose demo date is that day (immutable once past)
        2026-03-18.json
        ...
        index.json        ← {dates, counts, total, updated_at}

Each daily file is a JSON list of round dicts. Past days never change, so git
stores them once and every run only touches today's (small) file. No single
file ever approaches the size limit.
"""

import json
import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from .config import DEMOS_DIR

logger = logging.getLogger(__name__)

ROUNDS_DIR = os.path.join(DEMOS_DIR, "rounds")
INDEX_PATH = os.path.join(ROUNDS_DIR, "index.json")
LEGACY_PATH = os.path.join(DEMOS_DIR, "round_history.json")
PLAYER_ROUNDS_DIR = os.path.join(DEMOS_DIR, "player_rounds")


def safe_filename(name: str) -> str:
    """Filesystem-safe slug for a player name (matches scraper/history.py)."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", name)

# Demo filenames look like: tracker_2026_03_17_09_06_18_shipment_gpm_gungame_16.PRdemo
_DATE_RE = re.compile(r"tracker_(\d{4})_(\d{2})_(\d{2})")
UNKNOWN_DATE = "unknown"


def round_date(filename: str) -> str:
    """Return the ``YYYY-MM-DD`` partition key for a demo *filename*.

    Falls back to ``"unknown"`` when the date can't be parsed, so such rounds
    are still persisted (in ``unknown.json``) instead of silently dropped.
    """
    m = _DATE_RE.match(filename or "")
    if not m:
        return UNKNOWN_DATE
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"


def _day_files() -> list[str]:
    """Return sorted daily JSON filenames (excludes index.json)."""
    if not os.path.isdir(ROUNDS_DIR):
        return []
    return sorted(
        fn for fn in os.listdir(ROUNDS_DIR)
        if fn.endswith(".json") and fn != "index.json"
    )


def load_all_rounds() -> list[dict]:
    """Load every persisted round, in chronological-ish order.

    Reads the daily partitions when present; otherwise falls back to the legacy
    monolithic ``round_history.json`` so the scraper keeps working before the
    one-time migration has run.
    """
    if os.path.isdir(ROUNDS_DIR) and _day_files():
        rounds: list[dict] = []
        for fn in _day_files():
            try:
                with open(os.path.join(ROUNDS_DIR, fn)) as f:
                    rounds.extend(json.load(f))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Skipping unreadable round partition %s: %s", fn, exc)
        return rounds

    if os.path.exists(LEGACY_PATH):
        logger.info("No daily partitions yet; loading legacy %s", LEGACY_PATH)
        try:
            with open(LEGACY_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read legacy round history: %s", exc)

    return []


def append_rounds(new_rounds: list[dict]) -> None:
    """Append *new_rounds* into their daily partitions (dedup by filename).

    Only the day files actually touched are rewritten, so backfilled demos
    (which can arrive out of order) update just their own day. Rebuilds the
    index afterwards.
    """
    if not new_rounds:
        return

    os.makedirs(ROUNDS_DIR, exist_ok=True)

    by_date: dict[str, list[dict]] = defaultdict(list)
    for r in new_rounds:
        by_date[round_date(r.get("filename", ""))].append(r)

    for date, rounds in by_date.items():
        path = os.path.join(ROUNDS_DIR, f"{date}.json")
        existing: list[dict] = []
        seen: set = set()
        if os.path.exists(path):
            try:
                with open(path) as f:
                    existing = json.load(f)
                seen = {r.get("filename") for r in existing}
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Rewriting corrupt partition %s: %s", path, exc)
                existing, seen = [], set()

        added = 0
        for r in rounds:
            fname = r.get("filename")
            if fname not in seen:
                existing.append(r)
                seen.add(fname)
                added += 1

        if added:
            existing.sort(key=lambda r: r.get("filename", ""))
            with open(path, "w") as f:
                json.dump(existing, f)
            logger.info("Partition %s.json: +%d rounds (%d total)", date, added, len(existing))

    write_index()


def write_index() -> None:
    """Regenerate ``index.json`` from the daily partition files on disk."""
    os.makedirs(ROUNDS_DIR, exist_ok=True)
    counts: dict[str, int] = {}
    total = 0
    for fn in _day_files():
        try:
            with open(os.path.join(ROUNDS_DIR, fn)) as f:
                n = len(json.load(f))
        except (json.JSONDecodeError, OSError):
            n = 0
        counts[fn[:-5]] = n
        total += n

    index = {
        "dates": sorted(counts),
        "counts": counts,
        "total": total,
        "updated_at": datetime.now(timezone(timedelta(hours=-3))).strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(INDEX_PATH, "w") as f:
        json.dump(index, f, indent=2)


# ── Clan-player matching + precomputed leaderboards ─────────────────────────
#
# Kept here (stdlib only) so the bot's data and the one-time migration don't
# need the scraper's heavy deps (numpy/pandas/plotly).

LEADERBOARD_DIR = os.path.join(DEMOS_DIR, "leaderboards")
_LEADERBOARD_PERIODS = {"dia": 1, "semana": 7, "mes": 30, "todo": 0}
_ROUND_DT_RE = re.compile(r"tracker_(\d{4})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_")


class ClanMatcher:
    """Resolve a demo IGN to its canonical, case-sensitive prstats name.

    Demo IGNs may carry clan tags ("[LDH] juan*ARG*") while prstats stores bare
    names ("juan*ARG*"), so matching is by substring containment.

    prstats treats names case-sensitively: ``Dev.CO`` and ``Dev.Co`` (or
    ``TEJOTA4K`` and ``Tejota4K``) are *different accounts*. Blindly lowercasing
    would merge them. But players also sometimes type their name in a different
    case than they registered, so pure case-sensitive matching would drop ~2.6%
    of rounds. This matcher is two-tier to get both right:

      1. **Case-sensitive** exact match, then case-sensitive substring. When
         several names are substrings of the IGN (e.g. "andreesx_" and
         "andreesx_23"), the **longest** wins (ties broken alphabetically), so
         attribution is deterministic and most-specific.
      2. **Case-insensitive fallback**, but *only* when the lowercased name maps
         to a single account. Genuinely ambiguous collisions (a lowercased name
         shared by 2+ accounts) are left unmatched rather than merged into the
         wrong identity.

    ``clan_player_names is None`` means "accept everyone" (returns the lowercased
    IGN), used for unfiltered/migration runs.
    """

    def __init__(self, clan_player_names: set | None):
        self.names = None if clan_player_names is None else set(clan_player_names)
        self._cache: dict[str, str | None] = {}
        self._low_map: dict[str, set] = {}
        if self.names is not None:
            for n in self.names:
                self._low_map.setdefault(n.lower(), set()).add(n)

    def match(self, ign: str) -> str | None:
        if self.names is None:
            return ign.strip().lower()
        s = ign.strip()
        if s in self._cache:
            return self._cache[s]
        result = self._resolve(s)
        self._cache[s] = result
        return result

    def _resolve(self, s: str) -> str | None:
        # Tier 1a: case-sensitive exact match.
        if s in self.names:
            return s
        # Tier 1b: case-sensitive substring — longest, then alphabetical.
        best = _longest_substring(s, self.names)
        if best is not None:
            return best
        # Tier 2: case-insensitive fallback, unambiguous accounts only.
        il = s.lower()
        uniq = self._low_map.get(il)
        if uniq and len(uniq) == 1:
            return next(iter(uniq))
        unambiguous_lows = (low for low, orig in self._low_map.items() if len(orig) == 1)
        lbest = _longest_substring(il, unambiguous_lows)
        if lbest is not None:
            return next(iter(self._low_map[lbest]))
        return None


def _longest_substring(haystack: str, candidates) -> str | None:
    """Return the longest candidate contained in *haystack* (ties: alphabetical)."""
    best = None
    for c in candidates:
        if c in haystack:
            if best is None or len(c) > len(best) or (len(c) == len(best) and c < best):
                best = c
    return best


def _round_dt(filename: str):
    """Parse a demo *filename* into a tz-aware datetime (UTC-3), or None."""
    m = _ROUND_DT_RE.match(filename or "")
    if not m:
        return None
    return datetime(
        int(m.group(1)), int(m.group(2)), int(m.group(3)),
        int(m.group(4)), int(m.group(5)), int(m.group(6)),
        tzinfo=timezone(timedelta(hours=-3)),
    )


def build_leaderboards(rounds: list[dict], clan_player_names: set | None) -> None:
    """Precompute per-period clan-player leaderboards from *rounds*.

    Writes ``leaderboards/{dia,semana,mes,todo}.json``. Each holds aggregate
    stats per clan player over the rolling window, so the bot fetches one tiny
    file and sorts by any metric client-side. Matching mirrors the per-player
    aggregation (exact then substring) for consistent results.
    """
    os.makedirs(LEADERBOARD_DIR, exist_ok=True)
    now = datetime.now(timezone(timedelta(hours=-3)))
    generated_at = now.strftime("%Y-%m-%d %H:%M:%S")
    matcher = ClanMatcher(clan_player_names)

    for period, days in _LEADERBOARD_PERIODS.items():
        cutoff = (now - timedelta(days=days)) if days > 0 else None

        players: dict[str, dict] = {}
        rounds_in_period = 0
        for rd in rounds:
            if cutoff is not None:
                dt = _round_dt(rd.get("filename", ""))
                if dt is None or dt < cutoff:
                    continue
            rounds_in_period += 1
            for pdata in rd.get("players", {}).values():
                ign = pdata.get("ign", "").strip()
                if not ign:
                    continue
                matched = matcher.match(ign)
                if matched is None:
                    continue
                p = players.get(matched)
                if p is None:
                    p = players[matched] = {
                        "ign": matched, "kills": 0, "deaths": 0, "score": 0,
                        "rounds": 0, "revives": 0, "teamwork_score": 0,
                    }
                p["rounds"] += 1
                p["kills"] += pdata.get("kills", 0)
                p["deaths"] += pdata.get("deaths", 0)
                p["score"] += pdata.get("score", 0)
                p["revives"] += pdata.get("revives_given", 0)
                p["teamwork_score"] += pdata.get("teamwork_score", 0)

        ranked = sorted(players.values(), key=lambda p: p["kills"], reverse=True)
        payload = {
            "period": period,
            "days": days,
            "generated_at": generated_at,
            "total_rounds": rounds_in_period,
            "players": ranked,
        }
        with open(os.path.join(LEADERBOARD_DIR, f"{period}.json"), "w") as f:
            json.dump(payload, f)
        logger.info(
            "Leaderboard %s: %d players over %d rounds", period, len(ranked), rounds_in_period
        )


def build_player_rounds(rounds: list[dict], clan_player_names: set | None) -> None:
    """Write each clan player's per-round timeline for the web profile view.

    ``player_rounds/<safe_name>.json`` holds ``{player, rounds:[{date, map,
    gamemode, kills, deaths, score, won}]}`` sorted chronologically, plus an
    ``index.json`` mapping each player to its file + round count.

    Files are only rewritten when their content actually changed (past rounds
    are immutable), so a run that adds rounds for a handful of players rewrites
    just those files — keeping git churn minimal, the whole point of the
    redesign.
    """
    os.makedirs(PLAYER_ROUNDS_DIR, exist_ok=True)
    matcher = ClanMatcher(clan_player_names)

    by_player: dict[str, list] = defaultdict(list)
    for rd in sorted(rounds, key=lambda r: r.get("filename", "")):
        rdate = round_date(rd.get("filename", ""))
        rmap = rd.get("map_name", "unknown")
        gamemode = rd.get("gamemode", "unknown")
        winner = rd.get("winner", -1)
        for pdata in rd.get("players", {}).values():
            ign = pdata.get("ign", "").strip()
            if not ign:
                continue
            matched = matcher.match(ign)
            if matched is None:
                continue
            team = pdata.get("team", -1)
            by_player[matched].append({
                "date": rdate,
                "map": rmap,
                "gamemode": gamemode,
                "kills": pdata.get("kills", 0),
                "deaths": pdata.get("deaths", 0),
                "score": pdata.get("score", 0),
                "won": winner != -1 and team != -1 and winner == team,
            })

    written = 0
    index: dict[str, dict] = {}
    for player, prounds in by_player.items():
        safe = safe_filename(player)
        index[player] = {"file": f"{safe}.json", "rounds": len(prounds)}
        path = os.path.join(PLAYER_ROUNDS_DIR, f"{safe}.json")
        new_content = json.dumps({"player": player, "rounds": prounds}, ensure_ascii=False)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                if f.read() == new_content:
                    continue  # unchanged — skip to avoid git churn
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        written += 1

    index_payload = {
        "players": index,
        "updated_at": datetime.now(timezone(timedelta(hours=-3))).strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(PLAYER_ROUNDS_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index_payload, f, ensure_ascii=False)
    logger.info("Player rounds: %d players, %d files (re)written", len(by_player), written)


PLAYER_HEATMAP_DIR = os.path.join(DEMOS_DIR, "heatmaps", "players")


def build_player_heatmaps(rounds: list[dict], clan_player_names: set | None,
                          grid_size: int = 128) -> None:
    """Heatmap por jugador: dónde mata (kills, pos. del atacante) y dónde muere (deaths,
    pos. de la víctima), por mapa, gridado igual que los heatmaps de mapa (512/1024).

    Lee los nombres de `kill_positions` ([…, victim_ign, attacker_ign]) y los matchea a
    nombres de prstats (solo jugadores trackeados). Escribe diff-based
    `heatmaps/players/<safe>.json` = {player, grid_size, maps:{map:{kills,deaths}}} + index.
    Los nombres recién se capturan, así que arranca con poca data y crece."""
    os.makedirs(PLAYER_HEATMAP_DIR, exist_ok=True)
    matcher = ClanMatcher(clan_player_names)

    def grid(x, z, ms):
        if ms <= 0:
            return None
        full = ms * 1024.0
        nx = (x + ms * 512.0) / full
        nz = (z + ms * 512.0) / full
        if nx < 0 or nx > 1 or nz < 0 or nz > 1:
            return None
        return (min(grid_size - 1, int(nx * grid_size)), min(grid_size - 1, int(nz * grid_size)))

    by_player: dict = defaultdict(lambda: defaultdict(
        lambda: {"kills": defaultdict(int), "deaths": defaultdict(int)}))
    for rd in rounds:
        ms = rd.get("map_size", 0) or 0
        if ms <= 0:
            continue
        mapname = rd.get("map_name", "unknown")
        for e in (rd.get("kill_positions") or []):
            if len(e) < 10:        # rondas viejas sin nombres
                continue
            vign, aign = e[8], e[9]
            vm = matcher.match(vign) if vign else None
            if vm:
                c = grid(e[0], e[1], ms)
                if c:
                    by_player[vm][mapname]["deaths"][c] += 1
            am = matcher.match(aign) if aign else None
            if am and e[3] is not None:
                c = grid(e[3], e[4], ms)
                if c:
                    by_player[am][mapname]["kills"][c] += 1

    written = 0
    index: dict = {}
    for player, maps in by_player.items():
        safe = safe_filename(player)
        out_maps = {m: {"kills": [[gx, gy, c] for (gx, gy), c in d["kills"].items()],
                        "deaths": [[gx, gy, c] for (gx, gy), c in d["deaths"].items()]}
                    for m, d in maps.items()}
        index[player] = {"file": f"{safe}.json"}
        path = os.path.join(PLAYER_HEATMAP_DIR, f"{safe}.json")
        content = json.dumps({"player": player, "grid_size": grid_size, "maps": out_maps},
                             ensure_ascii=False)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                if f.read() == content:
                    continue
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        written += 1
    with open(os.path.join(PLAYER_HEATMAP_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"players": index}, f, ensure_ascii=False)
    logger.info("Player heatmaps: %d jugadores, %d archivos (re)escritos", len(by_player), written)
