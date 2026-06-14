"""Clan logo → Application Emoji mapping.

Clan emojis used to be hardcoded guild-emoji IDs in config.CLAN_EMOJIS, which
only render in the server that hosts them (and some were broken placeholders).
Application Emojis (discord.py 2.5+) are owned by the bot and render in *any*
server. Run ``-setup_emojis`` once to upload the clan logos; the resulting
``<:name:id>`` strings are cached here and used everywhere.

Falls back to the static config.CLAN_EMOJIS (now cleaned) until the upload runs.
"""

import json
import logging
import os
import re

logger = logging.getLogger(__name__)

_emoji_cache: dict[str, str] = {}
_EMOJI_FILE = "bot/data/clan_emojis.json"
_LOGOS_DIR = "logos"


def emoji_name_for(clan: str) -> str:
    """Application-emoji name for a clan (only [A-Za-z0-9_] allowed)."""
    return "Logo_" + re.sub(r"[^a-zA-Z0-9_]", "_", clan)


def load_clan_emoji_cache() -> None:
    if os.path.exists(_EMOJI_FILE):
        with open(_EMOJI_FILE) as f:
            _emoji_cache.update(json.load(f))
        logger.info("Loaded %d clan emojis from cache.", len(_emoji_cache))


def save_clan_emoji_cache() -> None:
    os.makedirs(os.path.dirname(_EMOJI_FILE), exist_ok=True)
    with open(_EMOJI_FILE, "w") as f:
        json.dump(_emoji_cache, f, indent=2)


def update_clan_emoji_cache(emoji_name: str, emoji_str: str) -> None:
    _emoji_cache[emoji_name] = emoji_str
    save_clan_emoji_cache()


def get_clan_emoji(clan: str) -> str:
    """Emoji string for a clan: app-emoji cache first, then static fallback."""
    cached = _emoji_cache.get(emoji_name_for(clan))
    if cached:
        return cached
    # Lazy import to avoid a circular import at module load.
    from bot.config import CLAN_EMOJIS
    return CLAN_EMOJIS.get(clan, "")


def get_all_clan_assets() -> list[tuple[str, str]]:
    """Return (emoji_name, logo_path) for every clan that has a logo file."""
    from bot.config import CLAN_NAMES
    assets: list[tuple[str, str]] = []
    for clan in CLAN_NAMES:
        for ext in ("png", "gif"):
            path = os.path.join(_LOGOS_DIR, f"Logo_{clan}.{ext}")
            if os.path.exists(path):
                assets.append((emoji_name_for(clan), path))
                break
    return assets
