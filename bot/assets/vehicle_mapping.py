"""Iconos de vehículos para el bot (Application Emojis).

Espeja el patrón de `kit_mapping`: los PNG viven en `bot/assets/vehicles/` (extraídos
del atlas oficial del juego, ver scraper/fetch_atlas.py + el atlas del realitytracker),
se suben como Application Emojis con `-setup_emojis` y se cachean en el mismo
`bot/data/kit_emojis.json` (keyed por nombre de emoji = nombre del icono).

`vehicle_icons.json` mapea code de vehículo → nombre de emoji (icono). `get_vehicle_emoji`
resuelve un code a su emoji usando el cache compartido.
"""

import json
import os

from .kit_mapping import get_emoji_by_name

_MAP_FILE = os.path.join(os.path.dirname(__file__), "vehicle_icons.json")
_ICON_DIR = os.path.join(os.path.dirname(__file__), "vehicles")

# code de vehículo → nombre de emoji (icono). Cargado una vez al importar.
try:
    with open(_MAP_FILE, encoding="utf-8") as _f:
        VEHICLE_ICON_MAP: dict = json.load(_f)
except (OSError, ValueError):
    VEHICLE_ICON_MAP = {}


def get_vehicle_emoji(code: str) -> str:
    """Emoji del icono oficial para un code de vehículo (o '' si no hay)."""
    icon = VEHICLE_ICON_MAP.get(code or "")
    return get_emoji_by_name(icon) if icon else ""


def get_all_vehicle_assets() -> list[tuple[str, str]]:
    """[(emoji_name, path)] de cada PNG en bot/assets/vehicles/ (para -setup_emojis)."""
    assets = []
    if os.path.isdir(_ICON_DIR):
        for fn in sorted(os.listdir(_ICON_DIR)):
            if fn.endswith(".png"):
                assets.append((fn[:-4], os.path.join(_ICON_DIR, fn)))
    return assets


# Mapa nombre-legible → code (para listas agregadas por nombre, sin code). Lazy: se arma
# tras cargar los aliases (clean_vehicle_name los usa).
_name_code: dict | None = None


def get_vehicle_emoji_by_name(name: str) -> str:
    """Emoji del icono por NOMBRE legible del vehículo (o '' si no hay)."""
    global _name_code
    if not name:
        return ""
    if _name_code is None:
        from .kit_mapping import clean_vehicle_name
        _name_code = {}
        for code in VEHICLE_ICON_MAP:
            nm = clean_vehicle_name(code)
            if nm and nm not in _name_code:
                _name_code[nm] = code
    code = _name_code.get(name)
    return get_vehicle_emoji(code) if code else ""
