"""History tracking with date-based deduplication."""

import json
import logging
import os
import re
from datetime import date
from typing import Any, Dict, List

import pandas as pd

from .config import HISTORY_DIR

logger = logging.getLogger(__name__)


def safe_filename(name: str) -> str:
    """Convert a player name to a filesystem-safe filename."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", name)


def _load_history(filepath: str) -> List[Dict[str, Any]]:
    """Load existing history JSON, handling corruption gracefully."""
    if not os.path.exists(filepath):
        return []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        logger.warning("History file %s is not a list — resetting.", filepath)
        return []
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Corrupted history file %s: %s — resetting.", filepath, exc)
        return []


def update_history(df: pd.DataFrame) -> None:
    """Update per-player history files with today's Performance Score.

    If an entry with today's date already exists, its score is updated
    instead of appending a duplicate.
    """
    os.makedirs(HISTORY_DIR, exist_ok=True)

    today_str = date.today().isoformat()  # YYYY-MM-DD only
    updated_count = 0
    created_count = 0

    for _, row in df.iterrows():
        player_name = row["Player"]
        score = row["Performance Score"]
        safe_name = safe_filename(player_name)
        filepath = os.path.join(HISTORY_DIR, f"{safe_name}_history.json")

        history = _load_history(filepath)

        # Check for existing entry with today's date
        found = False
        for entry in history:
            entry_date = entry.get("Date", "")
            # Handle both "YYYY-MM-DD" and "YYYY-MM-DD HH:MM:SS" formats
            if entry_date[:10] == today_str:
                entry["Date"] = today_str
                entry["Performance Score"] = score
                entry["scoring_version"] = "v3"
                found = True
                updated_count += 1
                break

        if not found:
            history.append({
                "Date": today_str,
                "Performance Score": score,
                "scoring_version": "v3",
            })
            created_count += 1

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4)
        except OSError as exc:
            logger.error("Failed to write history for %s: %s", player_name, exc)

    logger.info(
        "History update complete: %d new entries, %d updated entries.",
        created_count,
        updated_count,
    )
