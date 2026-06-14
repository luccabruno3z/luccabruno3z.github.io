"""Mapping from raw PR kit names to canonical kit categories.

Raw kit names from demos: 'usa_rifleman_ziptie', 'pl_medic_ziptie',
'taliban_medic', 'ru_assault_alt_iron', 'gungame_blue_rif_scope_6', etc.

All faction variants (us_, fr_, ru_, pl_, gb_, ch_, taliban_, insrg_, mec_, etc.)
and suffixes (_ziptie, _alt, _iron, _scope, _idx*) are normalized to the same
base kit. E.g. us_rifleman_ziptie, fr_rifleman, ru_rifleman_alt = "Fusilero".
"""

import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# (keyword, readable_name, emoji_name, asset_file)
# Order matters — first match wins. More specific keywords first.
KIT_CATEGORIES = [
    ("sniper", "Sniper", "pr_sniper", "kit_Sniper.png"),
    ("marksman", "Tirador", "pr_marksman", "kit_Marksman.png"),
    ("spotter", "Observador", "pr_spotter", "kit_Spotter.png"),
    ("medic", "Medico", "pr_medic", "kit_Medic.png"),
    ("officer", "Oficial", "pr_officer", "kit_Officer.png"),
    ("grenadier", "Granadero", "pr_grenadier", "kit_Grenadier.png"),
    ("breacher", "Breacher", "pr_engineer", "kit_Engineer.png"),
    ("machine_gun", "Ametralladora", "pr_mg", "kit_MG.png"),
    ("mg", "Ametralladora", "pr_mg", "kit_MG.png"),
    ("combat_engineer", "Ing. Combate", "pr_engineer", "kit_Engineer.png"),
    ("engineer", "Ingeniero", "pr_engineer", "kit_Engineer.png"),
    ("crewman", "Tripulante", "pr_crewman", "kit_Crewman.png"),
    ("pilot", "Piloto", "pr_pilot", "kit_Pilot.png"),
    ("specop", "Fuerzas Esp.", "pr_specops", "kit_Specops.png"),
    ("recon", "Reconocimiento", "pr_recon", "kit_recon.png"),
    ("aa", "Anti-Aereo", "pr_aa", "kit_AA.png"),
    ("hat", "HAT", "pr_at", "kit_AT.png"),
    ("lat", "LAT", "pr_at", "kit_AT.png"),
    ("anti-tank", "Anti-Tanque", "pr_at", "kit_AT.png"),
    ("at", "Anti-Tanque", "pr_at", "kit_AT.png"),
    ("rifleman_ap", "Fusilero AP", "pr_rifle", "kit_Rifle.png"),
    ("automatic_rifle", "Fus. Automatico", "pr_mg", "kit_MG.png"),
    ("assault", "Asalto", "pr_assault", "kit_Light_Assault.png"),
    ("rifleman", "Fusilero", "pr_rifle", "kit_Rifle.png"),
    ("rifle", "Fusilero", "pr_rifle", "kit_Rifle.png"),
    ("unarmed", "Desarmado", "pr_rifle", "kit_Rifle.png"),
]

_emoji_cache: dict[str, str] = {}
_EMOJI_FILE = "bot/data/kit_emojis.json"


def classify_kit(raw_name: str) -> tuple[str, str, str]:
    """Classify a raw kit name into (readable_name, emoji_name, asset_file)."""
    lower = raw_name.lower()
    if "gungame" in lower:
        return ("Gungame", "pr_rifle", "kit_Rifle.png")
    for keyword, readable, emoji_name, asset in KIT_CATEGORIES:
        if keyword in lower:
            return (readable, emoji_name, asset)
    return ("Otro", "pr_rifle", "kit_Rifle.png")


def get_kit_display(raw_name: str) -> str:
    """Get 'emoji ReadableName' for a raw kit name."""
    readable, emoji_name, _ = classify_kit(raw_name)
    emoji = _emoji_cache.get(emoji_name, "")
    return f"{emoji} {readable}" if emoji else readable


def normalize_kits(kits_dict: dict[str, int]) -> dict[str, int]:
    """Normalize a {raw_kit: count} dict by grouping faction variants.

    E.g. {'us_rifleman_ziptie': 5, 'fr_rifleman': 3, 'us_medic': 2}
    → {'Fusilero': 8, 'Medico': 2}
    """
    normalized: dict[str, int] = {}
    for raw, count in kits_dict.items():
        readable, _, _ = classify_kit(raw)
        normalized[readable] = normalized.get(readable, 0) + count
    return normalized


def get_kit_emoji(readable_name: str) -> str:
    """Get just the emoji string for a readable kit name (for inline use)."""
    for _, readable, emoji_name, _ in KIT_CATEGORIES:
        if readable == readable_name:
            return _emoji_cache.get(emoji_name, "")
    return ""


def load_emoji_cache() -> None:
    global _emoji_cache
    if os.path.exists(_EMOJI_FILE):
        with open(_EMOJI_FILE) as f:
            _emoji_cache.update(json.load(f))
        logger.info("Loaded %d kit emojis from cache.", len(_emoji_cache))


def save_emoji_cache() -> None:
    os.makedirs(os.path.dirname(_EMOJI_FILE), exist_ok=True)
    with open(_EMOJI_FILE, "w") as f:
        json.dump(_emoji_cache, f, indent=2)


def update_emoji_cache(emoji_name: str, emoji_str: str) -> None:
    _emoji_cache[emoji_name] = emoji_str
    save_emoji_cache()


def clean_weapon_name(raw: str) -> str:
    """Clean a raw weapon name into something readable.

    'usrif_m4scope' → 'M4 Scope'
    'gerlmg_mg34' → 'MG34'
    'apc_aavp7a1_PrimaryGun' → 'AAVP7A1'
    'ushgr_m67' → 'M67'
    """
    import re
    name = raw
    # Strip faction+type prefix: usrif_, rulmg_, gerlmg_, plrif_, insrg_, hmg_, etc.
    name = re.sub(
        r'^(?:us|ru|gb|ge|ch|pl|fr|mec|cf|mil|ins(?:rg)?|taliban|fsa|hamas|arf|ger|idf|nl|nva|vnnva|aus|arg|cdn|nz)?'
        r'(?:rif|lmg|mmg|hmg|smg|hgr|pis|sni|shg|at|aa|mg|car|rl|gl|apc|tnk|ahe|the|jet)?_?',
        '', name, flags=re.IGNORECASE
    )
    # Strip common suffixes
    name = re.sub(r'_?(?:deployed|scope|scopedeployed|iron|alt|idx\d+|gun|_r|_g|PrimaryGun|Coax_r|Coax_g|Maingun)$', '', name, flags=re.IGNORECASE)
    # Clean up
    name = name.strip('_').replace('_', ' ')
    if not name:
        name = raw.split('_')[-1]
    # Capitalize: short = uppercase, long = title
    if len(name) <= 6:
        name = name.upper()
    else:
        name = name.title()
    return name


def clean_vehicle_name(raw: str) -> str:
    """Clean a raw vehicle name: 'us_tnk_m1a2' → 'M1A2', 'ru_apc_bmp2' → 'BMP2'."""
    import re
    name = raw
    # Strip faction prefix
    name = re.sub(
        r'^(?:us|ru|gb|ge|ch|pl|fr|mec|cf|mil|ins(?:rg)?|taliban|fsa|hamas|idf|nl|nva|aus|arg|cdn|nz)_',
        '', name, flags=re.IGNORECASE
    )
    # Strip vehicle type prefix
    name = re.sub(
        r'^(?:tnk|apc|ifv|jep|trk|shp|the|ahe|aav|atm|box|jet|aav)_',
        '', name, flags=re.IGNORECASE
    )
    name = name.strip('_').replace('_', ' ')
    if not name:
        name = raw.split('_')[-1]
    if name.isupper() or name.islower():
        name = name.upper() if len(name) <= 6 else name.title()
    return name


def clean_map_name(raw: str) -> str:
    """Clean a raw map name: 'operation_falcon' → 'Operation Falcon'."""
    return raw.replace('_', ' ').title()


def get_all_assets() -> list[tuple[str, str]]:
    seen = set()
    assets = []
    for _, _, emoji_name, asset_file in KIT_CATEGORIES:
        if emoji_name not in seen:
            seen.add(emoji_name)
            path = os.path.join("bot", "assets", "kits", asset_file)
            if os.path.exists(path):
                assets.append((emoji_name, path))
    return assets
