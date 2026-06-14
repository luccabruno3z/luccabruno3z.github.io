"""Rank emoji mapping for tier badges.

Maps tier names to Application Emojis uploaded via -setup_emojis.
Falls back to unicode emojis if application emojis not available.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

# (tier_name, emoji_name, asset_file, unicode_fallback)
RANK_TIERS = [
    ("Elite", "rank_elite", "rank_elite.png", "⭐"),
    ("Veterano", "rank_veterano", "rank_veterano.png", "🎖️"),
    ("Experimentado", "rank_experimentado", "rank_experimentado.png", "🛡️"),
    ("Soldado", "rank_soldado", "rank_soldado.png", "⚔️"),
    ("Recluta", "rank_recluta", "rank_recluta.png", "🔰"),
]

_emoji_cache: dict[str, str] = {}
_EMOJI_FILE = "bot/data/rank_emojis.json"


def load_rank_emoji_cache() -> None:
    global _emoji_cache
    if os.path.exists(_EMOJI_FILE):
        with open(_EMOJI_FILE) as f:
            _emoji_cache.update(json.load(f))
        logger.info("Loaded %d rank emojis from cache.", len(_emoji_cache))


def save_rank_emoji_cache() -> None:
    os.makedirs(os.path.dirname(_EMOJI_FILE), exist_ok=True)
    with open(_EMOJI_FILE, "w") as f:
        json.dump(_emoji_cache, f, indent=2)


def update_rank_emoji_cache(emoji_name: str, emoji_str: str) -> None:
    _emoji_cache[emoji_name] = emoji_str
    save_rank_emoji_cache()


def get_rank_emoji(tier_name: str) -> str:
    """Get the emoji string for a tier name."""
    for name, emoji_name, _, fallback in RANK_TIERS:
        if name == tier_name:
            return _emoji_cache.get(emoji_name, fallback)
    return "🔰"


def get_all_rank_assets() -> list[tuple[str, str]]:
    """Return (emoji_name, asset_path) for all rank tiers."""
    assets = []
    for _, emoji_name, asset_file, _ in RANK_TIERS:
        path = os.path.join("bot", "assets", "ranks", asset_file)
        if os.path.exists(path):
            assets.append((emoji_name, path))
    return assets
