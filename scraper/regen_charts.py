"""Offline chart regenerator — rebuilds the interactive HTML charts from the
local JSON in `graphs/` WITHOUT touching the network or re-scraping.

Reads `graphs/all_players_clusters.json` (and falls back to concatenating the
per-clan `graphs/<CLAN>_players.json` files if the combined file is missing),
then regenerates:
  - graphs/all_players_interactive_chart.html
  - graphs/<CLAN>_interactive_chart.html  (one per clan present in the data)

Usage (from the repo root):
    /tmp/scraper_venv/bin/python -m scraper.regen_charts
    # or:
    python -m scraper.regen_charts
"""

import glob
import json
import logging
import os
import sys

import pandas as pd

# Allow running as `python scraper/regen_charts.py` too.
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "scraper"

from .charts import generate_all_players_chart, generate_clan_charts
from .config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def _load_dataframe() -> pd.DataFrame:
    """Load the all-players DataFrame from local JSON only."""
    combined = os.path.join(OUTPUT_DIR, "all_players_clusters.json")
    if os.path.exists(combined):
        logger.info("Loading %s", combined)
        df = pd.read_json(combined)
    else:
        logger.info("%s missing — concatenating per-clan JSON files.", combined)
        frames = []
        for path in sorted(glob.glob(os.path.join(OUTPUT_DIR, "*_players.json"))):
            frames.append(pd.read_json(path))
        if not frames:
            raise SystemExit(f"No player JSON found in {OUTPUT_DIR!r}.")
        df = pd.concat(frames, ignore_index=True)

    required = {"Player", "Clan", "K/D Ratio", "Score per Round", "Rounds", "Performance Score"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Input data is missing required columns: {sorted(missing)}")
    return df


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    df = _load_dataframe()
    logger.info("Loaded %d players across %d clans.", len(df), df["Clan"].nunique())

    # Regenerate charts for every clan actually present in the data (not just the
    # config list), so this works even if config and local JSON drift apart.
    clan_names = {c: c for c in sorted(df["Clan"].dropna().unique())}

    generate_all_players_chart(df)
    generate_clan_charts(df, clan_names)

    logger.info("Done. Regenerated charts for %d clans + the global chart.", len(clan_names))


if __name__ == "__main__":
    main()
