"""One-time migration: split the monolithic round_history.json into daily files.

The old ``graphs/demos/round_history.json`` grew to 100 MB and was re-committed
in full on every scraper run, bloating git history by tens of GB and eventually
hitting GitHub's 100 MB per-file push limit (breaking deploys).

This script reads that file, writes one ``rounds/<YYYY-MM-DD>.json`` per demo
date, builds ``rounds/index.json``, generates the initial period leaderboards,
and removes the monolith. It is idempotent: rerunning it on already-migrated
data simply rebuilds the partitions from whatever rounds exist.

Usage::

    python -m scraper.migrate_rounds
"""

import json
import logging
import os
import sys

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "scraper"

from .config import DEMOS_DIR
from .rounds_store import (
    LEGACY_PATH,
    ROUNDS_DIR,
    append_rounds,
    build_leaderboards,
    build_player_rounds,
    load_all_rounds,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("migrate_rounds")


def _load_clan_player_names() -> set[str] | None:
    """Recover clan player names (original case) from all_players_clusters.json.

    Original case is required so ClanMatcher can keep distinct case-only accounts
    (e.g. Dev.CO vs Dev.Co) separate.
    """
    path = os.path.join(os.path.dirname(DEMOS_DIR), "all_players_clusters.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            players = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    names = {p.get("Player", "") for p in players if p.get("Player")}
    return names or None


def main() -> None:
    # load_all_rounds() reads daily partitions if present, else the legacy file.
    rounds = load_all_rounds()
    if not rounds:
        logger.error("No rounds found (neither partitions nor %s). Nothing to do.", LEGACY_PATH)
        sys.exit(1)

    logger.info("Loaded %d rounds. Writing daily partitions under %s ...", len(rounds), ROUNDS_DIR)
    append_rounds(rounds)  # buckets by date, dedups, rebuilds index.json

    # Recover the clan player names from the existing all-players JSON so the
    # initial leaderboards are already filtered to clan members (matching the
    # bot's expectation). Falls back to unfiltered if the file is missing.
    clan_player_names = _load_clan_player_names()
    logger.info(
        "Building initial leaderboards (%s)...",
        f"{len(clan_player_names)} clan players" if clan_player_names else "unfiltered",
    )
    build_leaderboards(rounds, clan_player_names=clan_player_names)

    logger.info("Building per-player round timelines...")
    build_player_rounds(rounds, clan_player_names=clan_player_names)

    if os.path.exists(LEGACY_PATH):
        size_mb = os.path.getsize(LEGACY_PATH) / (1024 * 1024)
        os.remove(LEGACY_PATH)
        logger.info("Removed legacy monolith %s (%.1f MB).", LEGACY_PATH, size_mb)

    index_path = os.path.join(ROUNDS_DIR, "index.json")
    with open(index_path) as f:
        index = json.load(f)
    logger.info(
        "Done. %d daily partitions, %d total rounds. Index: %s",
        len(index.get("dates", [])), index.get("total", 0), index_path,
    )


if __name__ == "__main__":
    main()
