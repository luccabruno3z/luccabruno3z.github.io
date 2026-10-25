"""Estilo visual compartido de las tarjetas Components V2 (mismo lenguaje que la web).

- Colores por tier (borde de los Container) y la barra de "emojis" coloreada por tier:
  cada segmento es un Application Emoji (``tb_elite`` … ``tb_empty``, subidos con
  -setup_emojis desde bot/assets/bars/) con fallback a cuadrados unicode, así la barra
  se ve aunque los emojis todavía no estén subidos.
- El tier de un valor 0-1 usa los mismos umbrales que el Performance Score
  (tier_config.json → thresholds), así el color de una barra coincide con el rango.
- Nombres legibles de rondas (mapa · modo · fecha) y el bloque de récords de un
  jugador a partir de player_details.json.

Sin imports de cogs: se puede usar desde cualquier UI.
"""

from __future__ import annotations

import os
import re

from bot.config import PERFORMANCE_THRESHOLDS

# tier → (color del Container, nombre del emoji de segmento, fallback unicode)
TIERS: list[tuple[str, int, str, str]] = [
    ("Elite", 0xFFD700, "tb_elite", "🟨"),
    ("Veterano", 0x00FF88, "tb_veterano", "🟩"),
    ("Experimentado", 0x00BBFF, "tb_experimentado", "🟦"),
    ("Soldado", 0xFF8800, "tb_soldado", "🟧"),
    ("Recluta", 0xFF4466, "tb_recluta", "🟥"),
]
EMPTY_EMOJI = ("tb_empty", "⬛")
ACCENT = 0x00FFFF  # cian de la web, para tarjetas que no dependen de un tier
SEGMENTS = 8       # 8 segmentos: entra en mobile y no se come el límite de texto

_BARS_DIR = os.path.join("bot", "assets", "bars")
_FALLBACK_THRESHOLDS = {
    "elite": PERFORMANCE_THRESHOLDS[0][0],
    "veterano": PERFORMANCE_THRESHOLDS[1][0],
    "experimentado": PERFORMANCE_THRESHOLDS[2][0],
    "soldado": PERFORMANCE_THRESHOLDS[3][0],
}


def thresholds_or_default(thresholds: dict | None) -> dict:
    return thresholds if isinstance(thresholds, dict) and thresholds else _FALLBACK_THRESHOLDS


def tier_index(value: float, thresholds: dict | None = None) -> int:
    """Índice en TIERS para un valor 0-1 (0 = Elite … 4 = Recluta)."""
    thr = thresholds_or_default(thresholds)
    for i, key in enumerate(("elite", "veterano", "experimentado", "soldado")):
        if value >= thr.get(key, 1.0):
            return i
    return 4


def tier_color(value: float, thresholds: dict | None = None) -> int:
    return TIERS[tier_index(value, thresholds)][1]


def _emoji(name: str, fallback: str) -> str:
    from bot.assets.kit_mapping import get_emoji_by_name
    return get_emoji_by_name(name) or fallback


def meter(fraction: float, thresholds: dict | None = None, *, color_value: float | None = None,
          length: int = SEGMENTS) -> str:
    """Barra de emojis. ``fraction`` (0-1) decide cuánto se llena; ``color_value``
    (0-1, por defecto la misma fracción) decide el color según el tier."""
    fraction = max(0.0, min(1.0, fraction or 0.0))
    cv = fraction if color_value is None else color_value
    _, _, name, fb = TIERS[tier_index(cv, thresholds)]
    filled = round(fraction * length)
    return _emoji(name, fb) * filled + _emoji(*EMPTY_EMOJI) * (length - filled)


def accent_meter(fraction: float, length: int = SEGMENTS) -> str:
    """Barra en un solo color (cian) para métricas que no tienen tier (kills, rondas…)."""
    fraction = max(0.0, min(1.0, fraction or 0.0))
    filled = round(fraction * length)
    return _emoji("tb_accent", "🟦") * filled + _emoji(*EMPTY_EMOJI) * (length - filled)


def legend(thresholds: dict | None = None) -> str:
    """Leyenda corta de colores: '🟨 Élite ≥0,81 · 🟩 Veterano ≥0,70 · …'."""
    thr = thresholds_or_default(thresholds)
    keys = ("elite", "veterano", "experimentado", "soldado", None)
    parts = []
    for (tname, _c, ename, fb), key in zip(TIERS, keys):
        label = "Élite" if tname == "Elite" else tname
        cut = f" ≥{thr[key]:.2f}".replace(".", ",") if key else ""
        parts.append(f"{_emoji(ename, fb)} {label}{cut}")
    return " · ".join(parts)


def get_all_bar_assets() -> list[tuple[str, str]]:
    """[(emoji_name, path)] de los segmentos de barra, para -setup_emojis."""
    out = []
    if os.path.isdir(_BARS_DIR):
        for fn in sorted(os.listdir(_BARS_DIR)):
            if fn.endswith(".png"):
                out.append((fn[:-4], os.path.join(_BARS_DIR, fn)))
    return out


# ── Rondas y récords ───────────────────────────────────────────────────────────

_DEMO_RE = re.compile(r"tracker_(\d{4})_(\d{2})_(\d{2})_\d{2}_\d{2}_\d{2}_(.+?)_(gpm_[a-z_]+?)_\d+\.PRdemo$")


def round_label(rnd: dict) -> str:
    """'Battle of Debrecen · AAS · 27/06/2026' a partir de best_round/worst_round."""
    from bot.assets.kit_mapping import clean_map_name, clean_gamemode
    parts = [clean_map_name(str(rnd.get("map", "?")))]
    m = _DEMO_RE.search(str(rnd.get("filename", "")))
    if m:
        y, mo, d, _map, mode = m.groups()
        parts.append(clean_gamemode(mode))
        parts.append(f"{d}/{mo}/{y}")
    return " · ".join(parts)


def _pct(a: float, b: float) -> float:
    return a / b if b else 0.0


def player_records(dp: dict) -> dict | None:
    """Récords de un jugador de player_details.json, ya formateados para mostrar.

    Devuelve {best: {...}|None, items: [(label, value)], bars: [(label, fraction, shown)],
    rounds: int} o None si no hay datos de demos útiles."""
    if not isinstance(dp, dict) or not dp.get("rounds_played"):
        return None
    from bot.assets.kit_mapping import clean_map_name, clean_gamemode

    best = dp.get("best_round")
    best_out = None
    if isinstance(best, dict) and best.get("kills", 0) > 0:
        best_out = {
            "kills": best.get("kills", 0), "deaths": best.get("deaths", 0),
            "score": best.get("score", 0), "where": round_label(best),
        }

    items: list[tuple[str, str]] = []

    def add(label, value, *, keep_zero=False):
        if value or keep_zero:
            items.append((label, str(value)))

    add("Racha de kills", dp.get("best_killstreak", 0))
    add("Racha de victorias", dp.get("longest_win_streak", 0))
    add("Clutch kills", dp.get("total_clutch_kills", 0))
    add("First bloods", dp.get("total_first_bloods", 0))
    add("Vehículos destruidos", dp.get("total_vehicles_destroyed", 0))
    add("Revives dados", dp.get("total_revives_given", 0))

    maps = dp.get("maps_played") or {}
    if maps:
        top_map = max(maps.items(), key=lambda kv: kv[1])
        items.append(("Mapa más jugado", f"{clean_map_name(top_map[0])} ({top_map[1]})"))
    played = dp.get("played_seconds", 0) or 0
    if played >= 3600:
        items.append(("Tiempo registrado", f"{played / 3600:.0f} h"))

    bars: list[tuple[str, float, str]] = []
    wins, losses = dp.get("wins", 0) or 0, dp.get("losses", 0) or 0
    if wins + losses:
        wr = _pct(wins, wins + losses)
        bars.append((f"Winrate · {wins}–{losses}", wr, f"{wr * 100:.0f}%"))
    modes = [(m, s) for m, s in (dp.get("gamemode_stats") or {}).items() if s.get("rounds", 0) >= 5]
    if modes:
        mode, st = max(modes, key=lambda kv: kv[1].get("winrate", 0))
        wr = (st.get("winrate", 0) or 0) / 100
        bars.append((f"Mejor modo · {clean_gamemode(mode)}", wr, f"{wr * 100:.0f}%"))

    if not best_out and not items:
        return None
    return {"best": best_out, "items": items, "bars": bars, "rounds": dp.get("rounds_played", 0)}
