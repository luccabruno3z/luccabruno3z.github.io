"""JSON-backed per-guild settings store for data mode selection."""

import logging

from bot.services.storage import data_path, load_json, save_json

logger = logging.getLogger(__name__)

# Solo modos de datos ({guild_id: modo}). La config de automation (canal del
# leaderboard) vive aparte en automation.json: antes ambos compartían este archivo
# con formatos distintos y se pisaban.
DATA_FILE = data_path("guild_settings.json")
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
        """Load settings from disk (empty if missing or corrupt)."""
        data = load_json(DATA_FILE, {})
        # Descarta entradas que no sean un modo válido (p.ej. dicts que dejó la
        # versión anterior de automation al compartir el archivo).
        self._data = {
            k: v for k, v in data.items() if v in VALID_MODES
        } if isinstance(data, dict) else {}
        logger.info("Guild settings loaded (%d guilds)", len(self._data))

    def save(self) -> None:
        """Persist current settings to disk."""
        save_json(DATA_FILE, self._data)

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
