"""Orchestrator entrypoint for the PR Stats scraper.

Usage:
    python -m scraper
    python scraper/main.py
"""

import asyncio
import json
import logging
import math
import os
import re
import sys
from collections import defaultdict
import time
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

# Allow running as `python scraper/main.py` by adjusting sys.path
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "scraper"

from .aliases import build_aliases, resolve_kit, resolve_weapon
from .charts import generate_all_players_chart, generate_clan_charts
from .config import CLAN_URLS, OUTPUT_DIR, DEMOS_DIR, MAX_DEMOS_PER_RUN, DEMO_TIME_BUDGET, EXCLUDED_GAMEMODES
from .demo_fetcher import get_new_demo_urls, fetch_demo_batch, mark_processed, BATCH_SIZE
from .fetcher import fetch_all_clans
from .history import update_history
from .parser import parse_clan_html
from .prdemo import parse_demo, RoundStats
from .prdemo.decode import DemoReader
from .rounds_store import (
    load_all_rounds,
    append_rounds,
    ClanMatcher,
    build_leaderboards,
    build_player_rounds,
)
from .scoring import calculate_scores, compute_tier_thresholds
from .server_discovery import discover_servers

os.environ["OMP_NUM_THREADS"] = "1"

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure logging for the scraper."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def generate_logo_manifest(logos_dir: str = "logos") -> None:
    """Write logos/manifest.json = {clan: ext} from the actual logo files.

    The web reads this so clanLogoHTML knows which clans ship a logo without a
    hardcoded list (avoids both drift and 404s for logo-less clans)."""
    if not os.path.isdir(logos_dir):
        logger.warning("logos/ dir not found; skipping logo manifest.")
        return
    manifest: dict[str, str] = {}
    for fname in os.listdir(logos_dir):
        name, _, ext = fname.partition(".")
        if name.startswith("Logo_") and ext and name != "Logo_default":
            manifest[name[len("Logo_"):]] = ext.lower()
    path = os.path.join(logos_dir, "manifest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
    logger.info("Wrote %s (%d logos).", path, len(manifest))


def run() -> None:
    """Main scraper pipeline."""
    setup_logging()
    logger.info("Starting PR Stats scraper...")

    generate_logo_manifest()

    # 1. Fetch all clan pages in parallel
    html_pages = asyncio.run(fetch_all_clans())

    if not html_pages:
        logger.error("No clan data fetched. Aborting.")
        sys.exit(1)

    # 2. Parse HTML for each clan
    all_players = []
    all_warnings = []

    for clan_name, pages in html_pages.items():
        for html in pages:
            players, warnings = parse_clan_html(html, clan_name)
            all_players.extend(players)
            all_warnings.extend(warnings)

    if all_warnings:
        logger.warning("Total parsing warnings: %d", len(all_warnings))

    if not all_players:
        logger.error("No player data parsed. Aborting.")
        sys.exit(1)

    logger.info("Parsed %d total players from %d clans.", len(all_players), len(html_pages))

    # 3. Build DataFrame and clean
    df = pd.DataFrame(all_players)

    # Drop any player counted twice across pages (defensive: a roster row that
    # appears on a page boundary, or future pager quirks). Keep first occurrence.
    before = len(df)
    df = df.drop_duplicates(subset=["Player", "Clan"])
    if before != len(df):
        logger.warning("Removed %d duplicate player rows.", before - len(df))

    df = df.dropna()

    # Replace infinities (safety net — parser already handles division)
    df = df.replace([np.inf, -np.inf], np.nan).dropna()

    # 4. Calculate Performance Scores
    df = calculate_scores(df)

    # 5. Compute dynamic tier thresholds and generate tier_config.json
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now(timezone(timedelta(hours=-3))).strftime("%Y-%m-%d %H:%M:%S")

    thresholds = compute_tier_thresholds(df)
    ps_col = df["Performance Score"]
    tier_config = {
        "version": "v3",
        "generated_at": timestamp,
        "thresholds": thresholds,
        "target_distribution": [0.10, 0.30, 0.35, 0.20, 0.05],
        "predictor_weights": {"ps": 0.40, "kd": 0.25, "kpr": 0.15, "winrate": 0.20},
        "ps_stats": {
            "mean": round(float(ps_col.mean()), 4),
            "median": round(float(ps_col.median()), 4),
            "p95": round(float(ps_col.quantile(0.95)), 4),
            "max": round(float(ps_col.max()), 4),
        },
    }
    tier_config_path = os.path.join(OUTPUT_DIR, "tier_config.json")
    with open(tier_config_path, "w") as f:
        json.dump(tier_config, f, indent=2)
    logger.info("Saved %s (thresholds: %s)", tier_config_path, thresholds)

    # 6. Generate JSON outputs (backward compatible)
    # Add Last Updated to all players
    df["Last Updated"] = timestamp

    # All players JSON
    all_players_path = os.path.join(OUTPUT_DIR, "all_players_clusters.json")
    df.to_json(all_players_path, orient="records", lines=False)
    logger.info("Saved %s", all_players_path)

    # Clan averages JSON
    clan_averages = df.groupby("Clan")[[
        "Total Score",
        "Total Kills",
        "Total Deaths",
        "Rounds",
        "Kills per Round",
        "Score per Round",
        "Performance Score",
        "K/D Ratio",
    ]].mean().reset_index()

    averages_path = os.path.join(OUTPUT_DIR, "clan_averages.json")
    clan_averages.to_json(averages_path, orient="records", lines=False)
    logger.info("Saved %s", averages_path)

    # Per-clan JSONs

    for clan_name in CLAN_URLS:
        df_clan = df[df["Clan"] == clan_name]
        if df_clan.empty:
            logger.warning("No data for clan %s — skipping JSON.", clan_name)
            continue

        df_clan = df_clan.copy()
        df_clan["Last Updated"] = timestamp
        clan_path = os.path.join(OUTPUT_DIR, f"{clan_name}_players.json")
        df_clan.to_json(clan_path, orient="records", lines=False)
        logger.info("Saved %s", clan_path)

    # 7. Generate charts
    logger.info("Generating charts...")
    generate_all_players_chart(df)
    generate_clan_charts(df)

    # 8. Update player history
    logger.info("Updating player history...")
    update_history(df)

    # 9. Discover PR servers with demo files
    logger.info("Running server discovery...")
    try:
        discover_servers()
    except Exception as exc:
        logger.warning("Server discovery failed (will use fallback): %s", exc)

    # 10. Fetch and parse .PRdemo files from discovered/configured servers
    # Only keep demo data for players that belong to tracked clans.
    # Demo IGNs have clan tags (e.g. "[LDH] juan*ARG*") while prstats has
    # bare names ("juan*ARG*"), matched by ClanMatcher (case-sensitive, so
    # distinct case-only accounts like Dev.CO vs Dev.Co stay separate).
    clan_player_names = set(df["Player"].tolist())
    logger.info("Fetching new PRDemo files (filtering %d clan players)...", len(clan_player_names))
    _process_demos(timestamp, clan_player_names, df)

    logger.info("Scraper completed successfully.")


def _process_demos(timestamp: str, clan_player_names: set[str] | None = None, df=None) -> None:
    """Download, parse, and aggregate .PRdemo files into JSON outputs.

    Downloads in small batches to avoid running out of memory.
    Each batch is downloaded, parsed, saved, and then freed.

    Args:
        timestamp: Current run timestamp.
        clan_player_names: Set of lowercase player names from tracked clans.
            If provided, only these players are included in aggregated outputs.
        df: DataFrame with prstats data (used for name→clan mapping).
    """
    os.makedirs(DEMOS_DIR, exist_ok=True)

    # Load every previously persisted round from the daily-partitioned store
    # (falls back to the legacy round_history.json before migration has run).
    # Filtrar gungame (y otros modos excluidos): las rondas viejas quedan en disco
    # pero se ignoran en TODOS los agregados (player_details, map_stats, leaderboards,
    # player_rounds) — único punto de filtro.
    all_rounds = load_all_rounds()
    existing_rounds = [r for r in all_rounds if r.get("gamemode") not in EXCLUDED_GAMEMODES]
    dropped = len(all_rounds) - len(existing_rounds)
    if dropped:
        logger.info("Excluidas %d rondas de modos no competitivos (%s).",
                    dropped, ", ".join(sorted(EXCLUDED_GAMEMODES)))
    existing_filenames = {r.get("filename") for r in existing_rounds}

    # 1. Discover new demo URLs (lightweight — no downloads yet)
    try:
        new_urls = get_new_demo_urls()
    except Exception as exc:
        logger.error("Demo URL discovery failed: %s", exc)
        # Still refresh rolling-window leaderboards from what we already have.
        if existing_rounds:
            build_leaderboards(existing_rounds, clan_player_names)
        return

    if not new_urls:
        logger.info("No new demos to process.")
        # Rolling windows (día/semana/mes) shift over time, so refresh the
        # precomputed leaderboards even when there are no new demos.
        if existing_rounds:
            build_leaderboards(existing_rounds, clan_player_names)
        return

    total_available = len(new_urls)
    if MAX_DEMOS_PER_RUN > 0 and len(new_urls) > MAX_DEMOS_PER_RUN:
        new_urls = new_urls[:MAX_DEMOS_PER_RUN]
        logger.info(
            "Found %d new demos, processing %d this run (limit: %d/run). Rest picked up next run.",
            total_available, len(new_urls), MAX_DEMOS_PER_RUN,
        )
    else:
        logger.info("Found %d new demos to download and parse.", len(new_urls))

    # 2. (existing rounds already loaded above, before URL discovery)

    # 3. Process in batches to limit memory usage
    total_parsed = 0
    total_failed = 0
    newly_parsed: list[dict] = []
    demo_phase_start = time.monotonic()

    for batch_start in range(0, len(new_urls), BATCH_SIZE):
        # Check time budget before starting a new batch
        elapsed = time.monotonic() - demo_phase_start
        if DEMO_TIME_BUDGET > 0 and elapsed >= DEMO_TIME_BUDGET:
            remaining = len(new_urls) - batch_start
            logger.info(
                "Demo time budget exhausted (%.0fs >= %ds). %d demos deferred to next run.",
                elapsed, DEMO_TIME_BUDGET, remaining,
            )
            break

        batch_urls = new_urls[batch_start : batch_start + BATCH_SIZE]
        batch_num = (batch_start // BATCH_SIZE) + 1
        total_batches = (len(new_urls) + BATCH_SIZE - 1) // BATCH_SIZE
        logger.info("Batch %d/%d: downloading %d demos...", batch_num, total_batches, len(batch_urls))

        # Download batch
        try:
            batch_demos = asyncio.run(fetch_demo_batch(batch_urls))
        except Exception as exc:
            logger.error("Batch %d download failed: %s", batch_num, exc)
            continue

        # Parse each demo in batch
        parsed_filenames = []
        for filename, data in batch_demos:
            try:
                reader = DemoReader.from_bytes(data)
                round_stats = parse_demo(reader)
                round_dict = round_stats.to_dict()
                round_dict["filename"] = filename
                round_dict["processed_at"] = timestamp

                if filename not in existing_filenames:
                    existing_rounds.append(round_dict)
                    existing_filenames.add(filename)
                    newly_parsed.append(round_dict)

                total_parsed += 1
                parsed_filenames.append(filename)

                if round_stats.total_kills > 0:
                    logger.info(
                        "Parsed %s: %s (%s) — %d players, %d kills",
                        filename, round_stats.map_name, round_stats.gamemode,
                        len(round_stats.players), round_stats.total_kills,
                    )
            except Exception as exc:
                total_failed += 1
                logger.warning("Failed to parse %s (%d bytes): %s", filename, len(data), exc)

        # Only mark successfully parsed demos — failed ones will be retried next run
        mark_processed(parsed_filenames)
        # Free batch memory
        del batch_demos

    logger.info("Demo processing complete: %d parsed, %d failed.", total_parsed, total_failed)

    # 4. Persist newly parsed rounds into their daily partitions (append-only).
    #    Only the day files actually touched are rewritten, so git history stays
    #    tiny and no single file ever approaches the 100 MB push limit.
    if newly_parsed:
        append_rounds(newly_parsed)
        logger.info("Persisted %d new rounds into daily partitions.", len(newly_parsed))
    else:
        logger.info("No new rounds to persist.")

    if not existing_rounds:
        logger.warning("No round data available; nothing to aggregate.")
        return

    # 5. Re-aggregate per-player and per-map stats only when rounds changed.
    if newly_parsed:
        player_details = _aggregate_player_details(existing_rounds, clan_player_names, df)
        details_path = os.path.join(DEMOS_DIR, "player_details.json")
        with open(details_path, "w") as f:
            json.dump(player_details, f)
        logger.info("Saved %s (%d players)", details_path, len(player_details))

        map_stats = _aggregate_map_stats(existing_rounds)
        map_path = os.path.join(DEMOS_DIR, "map_stats.json")
        with open(map_path, "w") as f:
            json.dump(map_stats, f)
        logger.info("Saved %s (%d maps)", map_path, len(map_stats))

        # Humanized aliases for every raw asset code present (kits/weapons/
        # vehicles/maps/gamemodes). Single source of truth for web + bot.
        aliases = build_aliases(player_details, map_stats)
        aliases_path = os.path.join(DEMOS_DIR, "aliases.json")
        with open(aliases_path, "w", encoding="utf-8") as f:
            json.dump(aliases, f, ensure_ascii=False)
        logger.info("Saved %s (%s)", aliases_path,
                    ", ".join(f"{k}:{len(v)}" for k, v in aliases.items()))

        # Sinergia de dúo: rendimiento de cada jugador junto a sus compañeros de
        # escuadra frecuentes (se reconstruye desde todas las rondas con dato de squad).
        synergy = _aggregate_synergy(existing_rounds, clan_player_names)
        synergy_path = os.path.join(DEMOS_DIR, "synergy.json")
        with open(synergy_path, "w", encoding="utf-8") as f:
            json.dump(synergy, f, ensure_ascii=False)
        logger.info("Saved %s (%d players con sinergia)", synergy_path, len(synergy))

        # Heatmaps de muertes por mapa (grilla de densidad). Un archivo por mapa +
        # index, para que la web cargue solo el mapa pedido.
        heatmaps = _aggregate_heatmaps(existing_rounds)
        hm_dir = os.path.join(DEMOS_DIR, "heatmaps")
        os.makedirs(hm_dir, exist_ok=True)
        for mname, hm in heatmaps.items():
            safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", mname)
            with open(os.path.join(hm_dir, f"{safe}.json"), "w", encoding="utf-8") as f:
                json.dump(hm, f, ensure_ascii=False)
        with open(os.path.join(hm_dir, "index.json"), "w", encoding="utf-8") as f:
            json.dump(sorted(
                ({"map": m, "file": re.sub(r'[^a-zA-Z0-9_\-]', '_', m) + ".json",
                  "rounds": h["rounds"], "kills": h["deaths"]["kills"]} for m, h in heatmaps.items()),
                key=lambda e: e["kills"], reverse=True), f, ensure_ascii=False)
        logger.info("Saved %d heatmaps de mapa", len(heatmaps))

        # Per-player round timelines for the web profile view (diff-based write,
        # so only players with new rounds get their file rewritten).
        build_player_rounds(existing_rounds, clan_player_names)

    # 6. Rebuild precomputed period leaderboards for the Discord bot. Always run
    #    (rolling windows shift over time even with no new rounds).
    build_leaderboards(existing_rounds, clan_player_names)


def _aggregate_player_details(
    rounds: list[dict],
    clan_player_names: set[str] | None = None,
    df=None,
) -> list[dict]:
    """Aggregate per-player stats across all parsed rounds.

    Args:
        rounds: List of round dicts from round_history.json.
        clan_player_names: If provided, only include players whose prstats
            name (substring) matches the demo IGN.
        df: DataFrame with prstats data (unused for now, reserved).
    """
    players: dict[str, dict] = {}
    # Temporary accumulators for per-round data (used to compute derived fields)
    _acc: dict[str, dict] = {}
    # Two-tier case-sensitive matcher (respects distinct case-only accounts).
    matcher = ClanMatcher(clan_player_names)

    # Sort rounds chronologically by filename (contains date) for streak tracking
    sorted_rounds = sorted(rounds, key=lambda r: r.get("filename", ""))

    for round_data in sorted_rounds:
        round_winner = round_data.get("winner", -1)
        round_map = round_data.get("map_name", "unknown")
        round_gamemode = round_data.get("gamemode", "unknown")
        round_filename = round_data.get("filename", "")

        for pid, pdata in round_data.get("players", {}).items():
            ign = pdata.get("ign", "")
            if not ign:
                continue

            # Match demo IGN to prstats name
            matched = matcher.match(ign)
            if matched is None:
                continue

            # Use the prstats name as the key (not the demo IGN with clan tag)
            key = matched

            if key not in players:
                players[key] = {
                    "ign": key,
                    "rounds_played": 0,
                    "total_kills": 0,
                    "total_deaths": 0,
                    "total_score": 0,
                    "total_teamwork_score": 0,
                    "total_revives_given": 0,
                    "total_revives_received": 0,
                    "total_vehicles_destroyed": 0,
                    "total_flags_captured": 0,
                    "kits_used": {},
                    "kit_performance": {},  # rol -> {"kills","deaths"} (solo rondas nuevas)
                    "kill_weapons": {},
                    "death_weapons": {},
                    "vehicle_kills": {},
                    "vehicles_destroyed_by_type": {},  # vehículo → veces destruido
                    "seat_kills": {},                  # asiento → kills (artillero/conductor/piloto…)
                    "rounds_in_squad": 0,              # rondas en una escuadra (squad>0)
                    "rounds_with_squad_data": 0,       # denominador (solo rondas nuevas con dato de squad)
                    # Métricas nuevas (se acumulan desde las rondas nuevas):
                    "total_teamkills": 0,
                    "total_suicides_demo": 0,
                    "total_clutch_kills": 0,
                    "total_first_bloods": 0,
                    "best_killstreak": 0,              # máximo entre rondas
                    "alive_seconds": 0.0,             # tiempo vivo acumulado
                    "lives": 0,                        # vidas completadas (para vida promedio)
                    "cohesion_sum": 0.0,              # distancia al centroide de su escuadra
                    "cohesion_samples": 0,
                    "played_seconds": 0.0,            # duración de las rondas jugadas (para kills/min)
                    "maps_played": {},
                    # New fields
                    "wins": 0,
                    "losses": 0,
                    "rounds_per_gamemode": {},
                    "wins_per_gamemode": {},
                    "gamemode_stats": {},  # gm -> {rounds, wins, losses, kills, deaths, avg_kpr, avg_dpr}
                    "per_map_stats": {},
                    "faction_stats": {
                        "blufor": {"rounds": 0, "wins": 0, "avg_kpr": 0.0},
                        "opfor": {"rounds": 0, "wins": 0, "avg_kpr": 0.0},
                    },
                    "win_stats": {
                        "avg_kills_in_wins": 0.0,
                        "avg_kills_in_losses": 0.0,
                        "avg_deaths_in_wins": 0.0,
                        "avg_deaths_in_losses": 0.0,
                    },
                    "longest_win_streak": 0,
                    "longest_loss_streak": 0,
                }
                _acc[key] = {
                    "kills_per_round": [],
                    "deaths_per_round": [],
                    "win_sequence": [],  # True/False per round chronologically
                    "kills_in_wins": [],
                    "kills_in_losses": [],
                    "deaths_in_wins": [],
                    "deaths_in_losses": [],
                    "faction_kills": {"blufor": [], "opfor": []},
                }

            p = players[key]
            acc = _acc[key]

            round_kills = pdata.get("kills", 0)
            round_deaths = pdata.get("deaths", 0)
            round_score = pdata.get("score", 0)
            player_team = pdata.get("team", -1)

            # Basic accumulation (existing)
            p["rounds_played"] += 1
            p["total_kills"] += round_kills
            p["total_deaths"] += round_deaths
            p["total_score"] += round_score
            p["total_teamwork_score"] += pdata.get("teamwork_score", 0)
            p["total_revives_given"] += pdata.get("revives_given", 0)
            p["total_revives_received"] += pdata.get("revives_received", 0)
            p["total_vehicles_destroyed"] += pdata.get("vehicles_destroyed", 0)
            p["total_flags_captured"] += pdata.get("flags_captured", 0)

            for kit, count in pdata.get("kits_used", {}).items():
                p["kits_used"][kit] = p["kits_used"].get(kit, 0) + count
            # Desempeño por kit: agrupar kit_kills/kit_deaths crudos por ROL (alias),
            # consistente con normalize_kits del bot. Solo presente en rondas nuevas.
            for kit, count in pdata.get("kit_kills", {}).items():
                role = resolve_kit(kit)
                kp = p["kit_performance"].setdefault(role, {"kills": 0, "deaths": 0})
                kp["kills"] += count
            for kit, count in pdata.get("kit_deaths", {}).items():
                role = resolve_kit(kit)
                kp = p["kit_performance"].setdefault(role, {"kills": 0, "deaths": 0})
                kp["deaths"] += count
            for weapon, count in pdata.get("kill_weapons", {}).items():
                p["kill_weapons"][weapon] = p["kill_weapons"].get(weapon, 0) + count
            for weapon, count in pdata.get("death_weapons", {}).items():
                p["death_weapons"][weapon] = p["death_weapons"].get(weapon, 0) + count
            for veh, count in pdata.get("vehicle_kills", {}).items():
                p["vehicle_kills"][veh] = p["vehicle_kills"].get(veh, 0) + count
            for veh, count in pdata.get("vehicles_destroyed_by_type", {}).items():
                p["vehicles_destroyed_by_type"][veh] = p["vehicles_destroyed_by_type"].get(veh, 0) + count
            for seat, count in pdata.get("seat_kills", {}).items():
                p["seat_kills"][seat] = p["seat_kills"].get(seat, 0) + count
            if "squad" in pdata:  # solo rondas nuevas traen el dato de escuadra
                p["rounds_with_squad_data"] += 1
                if pdata["squad"]:
                    p["rounds_in_squad"] += 1
            # Métricas nuevas (rondas nuevas; .get tolera las viejas).
            p["total_teamkills"] += pdata.get("teamkills", 0)
            p["total_suicides_demo"] += pdata.get("suicides", 0)
            p["total_clutch_kills"] += pdata.get("clutch_kills", 0)
            p["total_first_bloods"] += pdata.get("first_blood", 0)
            p["best_killstreak"] = max(p["best_killstreak"], pdata.get("best_killstreak", 0))
            _tpt = round_data.get("demo_time_per_tick", 0) or 0
            p["alive_seconds"] += pdata.get("alive_ticks", 0) * _tpt
            p["lives"] += pdata.get("life_count", 0)
            p["cohesion_sum"] += pdata.get("cohesion_sum", 0)
            p["cohesion_samples"] += pdata.get("cohesion_samples", 0)
            if round_data.get("duration_seconds"):
                p["played_seconds"] += round_data["duration_seconds"]

            p["maps_played"][round_map] = p["maps_played"].get(round_map, 0) + 1

            # Per-round accumulation for new analytics
            acc["kills_per_round"].append(round_kills)
            acc["deaths_per_round"].append(round_deaths)

            # Win/loss determination
            won = (round_winner != -1 and player_team != -1 and round_winner == player_team)
            lost = (round_winner != -1 and player_team != -1 and round_winner != player_team)

            if won:
                p["wins"] += 1
                acc["win_sequence"].append(True)
                acc["kills_in_wins"].append(round_kills)
                acc["deaths_in_wins"].append(round_deaths)
            elif lost:
                p["losses"] += 1
                acc["win_sequence"].append(False)
                acc["kills_in_losses"].append(round_kills)
                acc["deaths_in_losses"].append(round_deaths)

            # Rounds/wins per gamemode
            p["rounds_per_gamemode"][round_gamemode] = p["rounds_per_gamemode"].get(round_gamemode, 0) + 1
            if won:
                p["wins_per_gamemode"][round_gamemode] = p["wins_per_gamemode"].get(round_gamemode, 0) + 1

            # Desempeño por gamemode (rondas/kills/deaths/wins → K/D, KPR, winrate)
            if round_gamemode not in p["gamemode_stats"]:
                p["gamemode_stats"][round_gamemode] = {
                    "rounds": 0, "_kills": [], "_deaths": [], "wins": 0, "losses": 0,
                }
            gs = p["gamemode_stats"][round_gamemode]
            gs["rounds"] += 1
            gs["_kills"].append(round_kills)
            gs["_deaths"].append(round_deaths)
            if won:
                gs["wins"] += 1
            elif lost:
                gs["losses"] += 1

            # Per-map stats accumulation
            if round_map not in p["per_map_stats"]:
                p["per_map_stats"][round_map] = {
                    "rounds": 0, "_kills": [], "_deaths": [], "wins": 0, "losses": 0,
                }
            ms = p["per_map_stats"][round_map]
            ms["rounds"] += 1
            ms["_kills"].append(round_kills)
            ms["_deaths"].append(round_deaths)
            if won:
                ms["wins"] += 1
            elif lost:
                ms["losses"] += 1

            # Faction stats accumulation (team 1 = blufor, team 2 = opfor)
            faction_key = None
            if player_team == 1:
                faction_key = "blufor"
            elif player_team == 2:
                faction_key = "opfor"
            if faction_key:
                p["faction_stats"][faction_key]["rounds"] += 1
                if won:
                    p["faction_stats"][faction_key]["wins"] += 1
                acc["faction_kills"][faction_key].append(round_kills)

            # Best/worst round tracking
            round_info = {
                "map": round_map,
                "kills": round_kills,
                "deaths": round_deaths,
                "score": round_score,
                "filename": round_filename,
            }
            if "best_round" not in p or round_kills > p.get("best_round", {}).get("kills", -1):
                p["best_round"] = round_info
            if "worst_round" not in p or round_kills < p.get("worst_round", {}).get("kills", float("inf")):
                p["worst_round"] = round_info

    # Second pass: compute derived fields
    for key, p in players.items():
        acc = _acc[key]
        kpr_list = acc["kills_per_round"]
        dpr_list = acc["deaths_per_round"]
        n = p["rounds_played"]

        # Averages
        p["avg_kpr"] = round(sum(kpr_list) / n, 2) if n > 0 else 0.0
        p["avg_dpr"] = round(sum(dpr_list) / n, 2) if n > 0 else 0.0

        # Teamwork ratio
        p["teamwork_ratio"] = round(p["total_teamwork_score"] / p["total_score"], 3) if p["total_score"] > 0 else 0.0

        # KPR standard deviation and consistency score
        # Filter out rounds with 0 kills (barely participated: gungame, joined late)
        active_kpr = [k for k in kpr_list if k > 0]
        n_active = len(active_kpr)
        if n_active >= 5:
            mean_kpr = sum(active_kpr) / n_active
            variance = sum((k - mean_kpr) ** 2 for k in active_kpr) / n_active
            std = math.sqrt(variance)
            p["kpr_stddev"] = round(std, 3)
            if mean_kpr > 0:
                coeff_of_variation = std / mean_kpr
                p["consistency_score"] = max(0, min(100, int(100 - (coeff_of_variation * 50))))
            else:
                p["consistency_score"] = 0
        else:
            p["kpr_stddev"] = 0.0
            p["consistency_score"] = -1  # -1 = not enough data

        # Win-conditional stats
        ws = p["win_stats"]
        ws["avg_kills_in_wins"] = round(sum(acc["kills_in_wins"]) / len(acc["kills_in_wins"]), 2) if acc["kills_in_wins"] else 0.0
        ws["avg_kills_in_losses"] = round(sum(acc["kills_in_losses"]) / len(acc["kills_in_losses"]), 2) if acc["kills_in_losses"] else 0.0
        ws["avg_deaths_in_wins"] = round(sum(acc["deaths_in_wins"]) / len(acc["deaths_in_wins"]), 2) if acc["deaths_in_wins"] else 0.0
        ws["avg_deaths_in_losses"] = round(sum(acc["deaths_in_losses"]) / len(acc["deaths_in_losses"]), 2) if acc["deaths_in_losses"] else 0.0

        # Faction avg_kpr
        for faction in ("blufor", "opfor"):
            fk = acc["faction_kills"][faction]
            p["faction_stats"][faction]["avg_kpr"] = round(sum(fk) / len(fk), 2) if fk else 0.0

        # Per-map stats: finalize averages and remove temp lists
        for map_name, ms in p["per_map_stats"].items():
            kills_list = ms.pop("_kills")
            deaths_list = ms.pop("_deaths")
            ms["avg_kpr"] = round(sum(kills_list) / len(kills_list), 2) if kills_list else 0.0
            ms["avg_dpr"] = round(sum(deaths_list) / len(deaths_list), 2) if deaths_list else 0.0

        # Per-gamemode stats: finalize KPR/DPR/KD/winrate y limpiar listas temp
        for gm, gs in p["gamemode_stats"].items():
            kills_list = gs.pop("_kills")
            deaths_list = gs.pop("_deaths")
            tk = sum(kills_list)
            td = sum(deaths_list)
            gs["kills"] = tk
            gs["deaths"] = td
            gs["avg_kpr"] = round(tk / len(kills_list), 2) if kills_list else 0.0
            gs["avg_dpr"] = round(td / len(deaths_list), 2) if deaths_list else 0.0
            gs["kd"] = round(tk / td, 2) if td > 0 else float(tk)
            gs["winrate"] = round(gs["wins"] / gs["rounds"] * 100, 1) if gs["rounds"] else 0.0

        # Streaks
        longest_win = 0
        longest_loss = 0
        cur_win = 0
        cur_loss = 0
        for w in acc["win_sequence"]:
            if w:
                cur_win += 1
                cur_loss = 0
                longest_win = max(longest_win, cur_win)
            else:
                cur_loss += 1
                cur_win = 0
                longest_loss = max(longest_loss, cur_loss)
        p["longest_win_streak"] = longest_win
        p["longest_loss_streak"] = longest_loss

        # Default best/worst round if somehow missing
        if "best_round" not in p:
            p["best_round"] = {"map": "unknown", "kills": 0, "deaths": 0, "score": 0, "filename": ""}
        if "worst_round" not in p:
            p["worst_round"] = {"map": "unknown", "kills": 0, "deaths": 0, "score": 0, "filename": ""}

    return sorted(players.values(), key=lambda p: p["total_kills"], reverse=True)


def _aggregate_map_stats(rounds: list[dict]) -> list[dict]:
    """Aggregate statistics per map across all parsed rounds."""
    maps: dict[str, dict] = {}

    for round_data in rounds:
        map_name = round_data.get("map_name", "unknown")
        gamemode = round_data.get("gamemode", "unknown")
        key = f"{map_name}_{gamemode}"

        if key not in maps:
            maps[key] = {
                "map_name": map_name,
                "gamemode": gamemode,
                "rounds_played": 0,
                "blufor_wins": 0,
                "opfor_wins": 0,
                "total_kills": 0,
                "total_revives": 0,
                "total_vehicles_destroyed": 0,
                "avg_tickets1_final": [],
                "avg_tickets2_final": [],
                "_durations": [],  # segundos de cada ronda (solo rondas nuevas)
            }

        m = maps[key]
        m["rounds_played"] += 1
        m["total_kills"] += round_data.get("total_kills", 0)
        m["total_revives"] += round_data.get("total_revives", 0)
        m["total_vehicles_destroyed"] += round_data.get("total_vehicles_destroyed", 0)
        if round_data.get("duration_seconds"):
            m["_durations"].append(round_data["duration_seconds"])

        winner = round_data.get("winner", -1)
        if winner == 1:
            m["blufor_wins"] += 1
        elif winner == 2:
            m["opfor_wins"] += 1

        m["avg_tickets1_final"].append(round_data.get("tickets1_final", 0))
        m["avg_tickets2_final"].append(round_data.get("tickets2_final", 0))

    # Compute averages
    result = []
    for m in maps.values():
        t1 = m.pop("avg_tickets1_final")
        t2 = m.pop("avg_tickets2_final")
        m["avg_tickets1_final"] = sum(t1) / len(t1) if t1 else 0
        m["avg_tickets2_final"] = sum(t2) / len(t2) if t2 else 0
        durs = m.pop("_durations")
        m["avg_duration_seconds"] = round(sum(durs) / len(durs), 1) if durs else 0
        result.append(m)

    return sorted(result, key=lambda m: m["rounds_played"], reverse=True)


def _aggregate_synergy(
    rounds: list[dict],
    clan_player_names: set[str] | None = None,
    min_shared: int = 2,
    max_mates: int = 40,
) -> dict:
    """Sinergia de dúo: por jugador, su rendimiento jugando en la MISMA escuadra
    que cada compañero frecuente.

    Dos jugadores son compañeros en una ronda si comparten (equipo, escuadra>0).
    Para cada par (P, Q) acumula las stats de P en las rondas con Q; el baseline de
    P (todas sus rondas con dato de escuadra) permite comparar "con Q vs sin Q".
    Solo rondas nuevas traen `squad`. Devuelve
    {P: {"baseline": {...}, "mates": {Q: {rounds,kills,deaths,wins}}}}."""
    matcher = ClanMatcher(clan_player_names)
    baseline: dict[str, dict] = defaultdict(lambda: {"rounds": 0, "kills": 0, "deaths": 0, "wins": 0})
    pairs: dict[str, dict] = defaultdict(lambda: defaultdict(lambda: {"rounds": 0, "kills": 0, "deaths": 0, "wins": 0}))

    for rd in rounds:
        winner = rd.get("winner", -1)
        squads: dict[tuple, list] = defaultdict(list)
        for pdata in rd.get("players", {}).values():
            if "squad" not in pdata:      # solo rondas nuevas tienen escuadra
                continue
            sq = pdata.get("squad", 0)
            if not sq:
                continue
            name = matcher.match(pdata.get("ign", ""))
            if not name:
                continue
            squads[(pdata.get("team", -1), sq)].append((name, pdata))

        for (team, _sq), members in squads.items():
            won = 1 if winner == team else 0
            # dedup por nombre (un jugador no puede ser su propio compañero)
            seen = set()
            uniq = []
            for name, pdata in members:
                if name in seen:
                    continue
                seen.add(name)
                uniq.append((name, pdata))
            for p_name, p_data in uniq:
                b = baseline[p_name]
                b["rounds"] += 1
                b["kills"] += p_data.get("kills", 0)
                b["deaths"] += p_data.get("deaths", 0)
                b["wins"] += won
                for q_name, _q in uniq:
                    if q_name == p_name:
                        continue
                    rec = pairs[p_name][q_name]
                    rec["rounds"] += 1
                    rec["kills"] += p_data.get("kills", 0)
                    rec["deaths"] += p_data.get("deaths", 0)
                    rec["wins"] += won

    out: dict[str, dict] = {}
    for p_name, mates in pairs.items():
        kept = {q: v for q, v in mates.items() if v["rounds"] >= min_shared}
        if not kept:
            continue
        kept = dict(sorted(kept.items(), key=lambda x: x[1]["rounds"], reverse=True)[:max_mates])
        out[p_name] = {"baseline": baseline[p_name], "mates": kept}
    return out


SNIPER_MIN_DIST = 150.0  # m: kills "a distancia" para la capa de francotiradores


def _aggregate_heatmaps(rounds: list[dict], grid_size: int = 128) -> dict:
    """Capas de densidad por mapa, acumuladas de TODAS las rondas (cada ronda suma).

    Todo se normaliza al centro del mapa (origen 0,0 = centro, mapa = `map_size` km):
    `nx = (x + map_size*500) / (map_size*1000)`. Capas por mapa:
      - `deaths`  : dónde muere cada equipo  → cells [[gx,gy,muertes_t1,muertes_t2]]
      - `movement`: rutas (densidad de paso) por equipo → {team1,team2}:[[gx,gy,c]]
      - `spawns`  : puntos de aparición por equipo → {team1,team2}:[[gx,gy,c]]
      - `sniper`  : posición del atacante en kills personales a >SNIPER_MIN_DIST,
                    por equipo del atacante → cells [[gx,gy,s1,s2]]
    Celdas dispersas; el render web suaviza."""
    def grid(x, z, msize):
        full = msize * 1000.0
        nx = (x + msize * 500.0) / full
        nz = (z + msize * 500.0) / full
        if nx < 0 or nx > 1 or nz < 0 or nz > 1:
            return None
        return (min(grid_size - 1, int(nx * grid_size)), min(grid_size - 1, int(nz * grid_size)))

    maps: dict[str, dict] = {}
    for rd in rounds:
        msize = rd.get("map_size", 0) or 0
        if msize <= 0:
            continue
        kps = rd.get("kill_positions")
        mv = rd.get("movement")
        sp = rd.get("spawns")
        if not (kps or mv or sp):
            continue
        mname = rd.get("map_name", "unknown")
        m = maps.get(mname)
        if m is None:
            m = maps[mname] = {
                "map": mname, "map_size": msize, "rounds": 0,
                "deaths": defaultdict(lambda: [0, 0]), "deaths_n": 0,
                "move": {1: defaultdict(int), 2: defaultdict(int)},
                "spawn": {1: defaultdict(int), 2: defaultdict(int)},
                "sniper": defaultdict(lambda: [0, 0]), "sniper_n": 0,
            }
        m["rounds"] += 1

        for e in (kps or []):
            cell = grid(e[0], e[1], msize)
            if cell is not None:
                m["deaths"][cell][1 if e[2] == 2 else 0] += 1
                m["deaths_n"] += 1
            # Francotiradores: atacante, kill personal a larga distancia.
            if len(e) >= 8 and e[3] is not None and (e[6] or -1) >= SNIPER_MIN_DIST:
                if e[7] != "?" and resolve_weapon(e[7]).get("kind") != "vehicle":
                    acell = grid(e[3], e[4], msize)
                    if acell is not None:
                        m["sniper"][acell][1 if e[5] == 2 else 0] += 1
                        m["sniper_n"] += 1

        if mv:
            mg = mv.get("grid", grid_size)
            for team in (1, 2):
                dst = m["move"][team]
                for gx, gy, c in mv.get(f"team{team}", []):
                    if mg != grid_size:
                        gx = gx * grid_size // mg
                        gy = gy * grid_size // mg
                    dst[(gx, gy)] += c

        for x, z, team in (sp or []):
            if team in (1, 2):
                cell = grid(x, z, msize)
                if cell is not None:
                    m["spawn"][team][cell] += 1

    def cells2(d):
        out = [[gx, gy, c[0], c[1]] for (gx, gy), c in d.items()]
        out.sort(key=lambda e: e[2] + e[3], reverse=True)
        return out

    def cells1(d):
        out = [[gx, gy, c] for (gx, gy), c in d.items()]
        out.sort(key=lambda e: e[2], reverse=True)
        return out

    result: dict[str, dict] = {}
    for mname, m in maps.items():
        result[mname] = {
            "map": mname, "map_size": m["map_size"], "grid_size": grid_size,
            "rounds": m["rounds"],
            "deaths": {"kills": m["deaths_n"], "cells": cells2(m["deaths"])},
            "movement": {"team1": cells1(m["move"][1]), "team2": cells1(m["move"][2])},
            "spawns": {"team1": cells1(m["spawn"][1]), "team2": cells1(m["spawn"][2])},
            "sniper": {"threshold_m": SNIPER_MIN_DIST, "kills": m["sniper_n"],
                       "cells": cells2(m["sniper"])},
        }
    return result


if __name__ == "__main__":
    run()
