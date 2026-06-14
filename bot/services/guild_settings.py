"""JSON-backed per-guild settings store for data mode selection."""

import json
import logging
import os

logger = logging.getLogger(__name__)

DATA_FILE = "bot/data/guild_settings.json"
VALID_MODES = ("prstats", "demos", "combined")
DEFAULT_MODE = "combined"


class GuildSettings:
    """Manages per-guild data mode preferences.

    Modes:
        - ``prstats``: Only data from prstats.realitymod.org (basic stats).
        - ``demos``: Only data from parsed .PRdemo files (detailed stats).
        - ``combined``: Both sources merged (default).
    """

    def __init__(self):
        self._data: dict[str, str] = {}
        self.load()

    def load(self) -> None:
        """Load settings from disk, creating the file if missing."""
        if not os.path.exists(DATA_FILE):
            os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
            self._data = {}
            self.save()
            return

        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            logger.info("Guild settings loaded (%d guilds)", len(self._data))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load guild settings: %s — starting fresh", e)
            self._data = {}

    def save(self) -> None:
        """Persist current settings to disk."""
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error("Failed to save guild settings: %s", e)

    def get_mode(self, guild_id: int) -> str:
        """Return the data mode for a guild, defaulting to ``combined``."""
        return self._data.get(str(guild_id), DEFAULT_MODE)

    def set_mode(self, guild_id: int, mode: str) -> bool:
        """Set the data mode for a guild.

        Returns ``True`` on success, ``False`` if the mode is invalid.
        """
        if mode not in VALID_MODES:
            return False
        self._data[str(guild_id)] = mode
        self.save()
        logger.info("Guild %s data mode set to '%s'", guild_id, mode)
        return True
