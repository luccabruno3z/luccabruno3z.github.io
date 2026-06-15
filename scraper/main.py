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
import sys
import time
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

# Allow running as `python scraper/main.py` by adjusting sys.path
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "scraper"

from .charts import generate_all_players_chart, generate_clan_charts
from .config import CLAN_URLS, OUTPUT_DIR, DEMOS_DIR, MAX_DEMOS_PER_RUN, DEMO_TIME_BUDGET
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


def run() -> None:
    """Main scraper pipeline."""
    setup_logging()
    logger.info("Starting PR Stats scraper...")

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
    df = pd.DataFrame(all_players).dropna()

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
    existing_rounds = load_all_rounds()
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
                    "kill_weapons": {},
                    "death_weapons": {},
                    "vehicle_kills": {},
                    "maps_played": {},
                    # New fields
                    "wins": 0,
                    "losses": 0,
                    "rounds_per_gamemode": {},
                    "wins_per_gamemode": {},
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
            for weapon, count in pdata.get("kill_weapons", {}).items():
                p["kill_weapons"][weapon] = p["kill_weapons"].get(weapon, 0) + count
            for weapon, count in pdata.get("death_weapons", {}).items():
                p["death_weapons"][weapon] = p["death_weapons"].get(weapon, 0) + count
            for veh, count in pdata.get("vehicle_kills", {}).items():
                p["vehicle_kills"][veh] = p["vehicle_kills"].get(veh, 0) + count

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
            }

        m = maps[key]
        m["rounds_played"] += 1
        m["total_kills"] += round_data.get("total_kills", 0)
        m["total_revives"] += round_data.get("total_revives", 0)
        m["total_vehicles_destroyed"] += round_data.get("total_vehicles_destroyed", 0)

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
        result.append(m)

    return sorted(result, key=lambda m: m["rounds_played"], reverse=True)


if __name__ == "__main__":
    run()
