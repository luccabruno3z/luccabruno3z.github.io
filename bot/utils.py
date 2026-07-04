"""Shared formatting utilities for the LDH Stats bot."""

import math
from datetime import datetime, timezone, timedelta

UTC_MINUS_3 = timezone(timedelta(hours=-3))


def format_number(n) -> str:
    """Format a number with thousands separators. 1234567 -> '1,234,567'."""
    if n is None:
        return "N/A"
    if isinstance(n, float):
        if n == int(n) and abs(n) > 100:
            return f"{int(n):,}"
        return f"{n:,.2f}"
    return f"{n:,}"


def progress_bar(value: float, max_value: float, length: int = 10) -> str:
    """Unicode progress bar. progress_bar(7, 10) -> '▓▓▓▓▓▓▓░░░'."""
    if max_value <= 0:
        return "░" * length
    ratio = min(max(value / max_value, 0), 1.0)
    filled = round(ratio * length)
    return "▓" * filled + "░" * (length - filled)


def percentile(player_value: float, all_values: list[float]) -> str:
    """Calculate percentile. Returns 'top 5%' style string."""
    if not all_values:
        return "N/A"
    count_below = sum(1 for v in all_values if v < player_value)
    pct = (count_below / len(all_values)) * 100
    top_pct = 100 - pct
    if top_pct < 1:
        return "top 1%"
    return f"top {top_pct:.0f}%"


_DEFAULT_THRESHOLDS = {"elite": 0.70, "veterano": 0.55, "experimentado": 0.40, "soldado": 0.25}


def _tier_name(score: float, thresholds: dict | None = None) -> str:
    """Get tier name from score using dynamic or default thresholds."""
    t = thresholds or _DEFAULT_THRESHOLDS
    if score >= t["elite"]:
        return "Elite"
    elif score >= t["veterano"]:
        return "Veterano"
    elif score >= t["experimentado"]:
        return "Experimentado"
    elif score >= t["soldado"]:
        return "Soldado"
    return "Recluta"


def tier_badge(score: float, thresholds: dict | None = None) -> str:
    """Performance tier badge with emoji and name."""
    from bot.assets.rank_mapping import get_rank_emoji
    name = _tier_name(score, thresholds)
    emoji = get_rank_emoji(name)
    return f"{emoji} {name}"


def tier_emoji(score: float, thresholds: dict | None = None) -> str:
    """Just the tier emoji."""
    from bot.assets.rank_mapping import get_rank_emoji
    return get_rank_emoji(_tier_name(score, thresholds))


def rank_medal(position: int) -> str:
    """Medal emoji for top 3 positions."""
    if position == 1:
        return "🥇"
    elif position == 2:
        return "🥈"
    elif position == 3:
        return "🥉"
    return f"#{position}"


def highlight_winner(val1: float, val2: float, higher_is_better: bool = True):
    """Returns (emoji1, emoji2) indicating winner/loser."""
    if val1 == val2:
        return ("🟰", "🟰")
    if higher_is_better:
        return ("✅", "❌") if val1 > val2 else ("❌", "✅")
    return ("✅", "❌") if val1 < val2 else ("❌", "✅")


def advantage_pct(val1: float, val2: float) -> str:
    """Calculate advantage percentage. Returns '+25.3%' or '-12.1%'."""
    if val2 == 0:
        return "+∞%" if val1 > 0 else "0%"
    pct = ((val1 - val2) / abs(val2)) * 100
    return f"{pct:+.1f}%"


def _vt_num(v: float) -> str:
    """Número compacto para la tabla de -compare (ancho fijo, sin decimales de más)."""
    if isinstance(v, float) and not float(v).is_integer():
        return f"{v:,.2f}" if abs(v) < 1000 else f"{v:,.0f}"
    return f"{int(v):,}"


def versus_table(name1: str, name2: str, metrics: list[tuple]) -> tuple[str, int, int, int]:
    """Tabla monoespaciada head-to-head para -compare (una ▲ marca al mejor por fila).

    Reemplaza las líneas ❌/✅+emoji+negritas (ruido visual) por columnas alineadas.
    *metrics*: lista de (label, v1, v2, higher_is_better).
    Devuelve (bloque_markdown, wins1, wins2, ties). El % es la ventaja del ganador
    (negativo en métricas lower-is-better, p.ej. -12% = 12% menos muertes).
    """
    c1, c2 = name1[:9], name2[:9]
    rows = [f"{'':<13}{c1:>9}  {c2:>9}"]
    wins1 = wins2 = ties = 0
    for label, v1, v2, hib in metrics:
        win1 = (v1 > v2) if hib else (v1 < v2)
        win2 = (v2 > v1) if hib else (v2 < v1)
        if win1:
            wins1 += 1
        elif win2:
            wins2 += 1
        else:
            ties += 1
        m1 = "▲" if win1 else " "
        m2 = "▲" if win2 else " "
        pct = advantage_pct(v1, v2) if win1 else (advantage_pct(v2, v1) if win2 else "=")
        rows.append(f"{label:<13.13}{_vt_num(v1):>8}{m1} {_vt_num(v2):>8}{m2} {pct:>7}")
    return "```\n" + "\n".join(rows) + "\n```", wins1, wins2, ties


def find_player(data: list[dict], name: str, key: str = "Player") -> dict | None:
    """Find a player by name with priority cascade:

    1. Exact match (case-sensitive): "TEJOTA4K" finds "TEJOTA4K" not "Tejota4k"
    2. Exact match (case-insensitive): "tejota4k" finds whichever comes first
    3. Partial/contains match: "juan" finds "juan*ARG*"

    This preserves case-sensitivity for players with duplicate names in
    different casing (e.g. TEJOTA4K vs Tejota4k) while still allowing
    flexible search for names with special characters.

    `key` selecciona el campo del nombre: "Player" para los datos de prstats,
    "ign" para los datos de demos (player_details). Así toda búsqueda de jugador
    usa exactamente la misma cascada (uniforme entre comandos).
    """
    if not isinstance(data, list) or not name:
        return None

    # 1. Exact match (case-sensitive) — highest priority
    for p in data:
        if p.get(key) == name:
            return p

    # 2. Exact match (case-insensitive)
    name_lower = name.lower()
    for p in data:
        if (p.get(key) or "").lower() == name_lower:
            return p

    # 3. Partial/contains match (case-insensitive)
    for p in data:
        if name_lower in (p.get(key) or "").lower():
            return p

    return None


def relative_time(timestamp_str: str) -> str:
    """Convert '2026-03-17 00:05:02' to 'hace 2 horas'. Assumes timestamp is UTC-3."""
    try:
        dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC_MINUS_3)
        now = datetime.now(UTC_MINUS_3)
        delta = now - dt
        seconds = delta.total_seconds()

        if seconds < 60:
            return "hace un momento"
        elif seconds < 3600:
            mins = int(seconds / 60)
            return f"hace {mins} min"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"hace {hours}h"
        else:
            days = int(seconds / 86400)
            return f"hace {days}d"
    except (ValueError, TypeError):
        return timestamp_str


def classify_playstyle(kd: float, kills_per_round: float, deaths_per_round: float, rounds: int) -> tuple[str, str]:
    """Classify player's style based on stats. Returns (emoji, name)."""
    if kd >= 2.0 and kills_per_round < 3.0:
        return ("🎯", "Francotirador")
    elif kills_per_round >= 5.0 and deaths_per_round >= 4.0:
        return ("🗡️", "Asesino")
    elif deaths_per_round < 2.5 and kd >= 1.2:
        return ("🛡️", "Superviviente")
    elif rounds >= 500 and 0.8 <= kd <= 1.8:
        return ("⭐", "Veterano")
    elif kills_per_round >= 4.0 and rounds >= 200:
        return ("🏋️", "Tanque")
    elif rounds < 50:
        return ("🌱", "Novato")
    else:
        return ("⚔️", "Soldado")


def score_breakdown(player: dict) -> str:
    """Show Performance Score component breakdown with progress bars and descriptions."""
    norm_kd = player.get("Normalized_KD", 0)
    norm_score = player.get("Normalized_Score", 0)
    norm_kpr = player.get("Normalized_Kills_Per_Round", 0)
    norm_rounds = player.get("Normalized_Rounds", 0)

    # Components with short descriptions
    components = [
        ("Combate", norm_kd, "Kills vs muertes"),
        ("Puntuación", norm_score, "Score por ronda"),
        ("Agresividad", norm_kpr, "Kills por ronda"),
        ("Experiencia", norm_rounds, "Rondas jugadas"),
    ]

    values = {name: val for name, val, _ in components}
    bottleneck = min(values, key=values.get)
    best = max(values, key=values.get)

    lines = []
    for name, val, desc in components:
        bar = progress_bar(val, 1.0, 8)
        tag = ""
        if name == bottleneck and val < 0.7:
            tag = " ⚠️"
        elif name == best:
            tag = " ⭐"
        lines.append(f"`{bar}` **{val:.2f}** {name}{tag}\n╰ *{desc}*")

    lines.append(f"\n⭐ = tu mejor stat · ⚠️ = área de mejora")

    return "\n".join(lines)


def experience_badge(rounds: int) -> str:
    """Experience tier based on rounds played."""
    if rounds >= 1000:
        return "🎖️ Leyenda"
    elif rounds >= 500:
        return "⭐ Veterano"
    elif rounds >= 200:
        return "⚔️ Experimentado"
    elif rounds >= 50:
        return "🛡️ Regular"
    elif rounds >= 10:
        return "🌱 Novato"
    else:
        return "❓ Sin datos suficientes"


def sample_reliability(rounds: int) -> str:
    """How reliable are this player's stats based on sample size."""
    if rounds >= 200:
        return "🟢 Alta confiabilidad"
    elif rounds >= 50:
        return "🟡 Confiabilidad media"
    elif rounds >= 10:
        return "🟠 Baja confiabilidad"
    else:
        return "🔴 Datos insuficientes"


def sigmoid_penalty_display(rounds: int) -> str:
    """Show the sigmoid penalty as text for the user."""
    penalty = 1.0 / (1.0 + math.exp(-((rounds - 25) / 10)))
    pct = penalty * 100
    if pct >= 95:
        return ""  # No penalty worth mentioning
    rounds_for_95 = 25 + 10 * math.log(19)  # ~54.4 rounds
    remaining = max(0, int(rounds_for_95) - rounds)
    return f"⚠️ Penalización: {pct:.0f}% (necesitás ~{remaining} rondas más)"


def stat_confidence_warning(rounds: int) -> str:
    """Returns a warning string if sample size is too low, empty otherwise."""
    if rounds < 10:
        return "\n⚠️ **Pocas rondas** — estos stats pueden no ser representativos"
    elif rounds < 50:
        return "\n🟡 **Muestra limitada** — stats se estabilizan con más rondas"
    return ""


def activity_index_display(activity_index: float) -> str:
    """Format Activity Index (0-100) with visual bar and tier label."""
    if activity_index is None:
        return "N/A"
    bar = progress_bar(activity_index, 100.0, 8)
    if activity_index >= 80:
        tier = "🔥 Muy Activo"
    elif activity_index >= 60:
        tier = "✅ Activo"
    elif activity_index >= 40:
        tier = "🟡 Moderado"
    elif activity_index >= 20:
        tier = "🟠 Bajo"
    else:
        tier = "❄️ Inactivo"
    return f"`{bar}` {activity_index:.1f}/100 — {tier}"


def standard_footer(data_or_timestamp=None) -> str:
    """Unified footer format for all embeds showing player data."""
    if isinstance(data_or_timestamp, list) and data_or_timestamp:
        ts = data_or_timestamp[0].get("Last Updated", "")
    elif isinstance(data_or_timestamp, dict):
        ts = data_or_timestamp.get("Last Updated", "")
    elif isinstance(data_or_timestamp, str):
        ts = data_or_timestamp
    else:
        ts = ""

    if ts:
        rel = relative_time(ts)
        # Format raw timestamp as dd/mm/yyyy HH:MM
        try:
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            formatted = dt.strftime("%d/%m/%Y %H:%M")
        except (ValueError, TypeError):
            formatted = ts
        return f"📅 {rel} · {formatted} (UTC-3)"

    now = datetime.now(UTC_MINUS_3).strftime("%d/%m/%Y %H:%M")
    return f"📅 {now} (UTC-3)"


def get_player_archetype(player: dict) -> tuple[str, str]:
    """Read pre-computed archetype from player JSON. Falls back to classify_playstyle."""
    arch = player.get("archetype")
    if arch and isinstance(arch, dict):
        return (arch.get("emoji", "⚔️"), arch.get("name", "Soldado"))
    kd = player.get("K/D Ratio", 0)
    kpr = player.get("Kills per Round", 0)
    rounds = player.get("Rounds", 0)
    total_deaths = player.get("Total Deaths", 0)
    dpr = total_deaths / rounds if rounds > 0 else 0
    return classify_playstyle(kd, kpr, dpr, rounds)


def get_player_archetype_desc(player: dict) -> str:
    """Get archetype description from pre-computed data."""
    arch = player.get("archetype")
    if arch and isinstance(arch, dict):
        return arch.get("desc", "")
    return ""


def get_player_radar(player: dict) -> dict | None:
    """Extract pre-computed 6-axis radar profile from player JSON."""
    return player.get("radar")


def get_player_ratings(player: dict) -> dict | None:
    """Extract pre-computed composite ratings (0-100) from player JSON."""
    return player.get("ratings")


def ratings_display(ratings: dict) -> str:
    """Format 4 composite ratings with progress bars."""
    if not ratings:
        return ""
    labels = {
        "combat": ("⚔️", "Combate"),
        "tactical": ("🎯", "Táctico"),
        "reliability": ("🛡️", "Fiabilidad"),
        "impact": ("💥", "Impacto"),
    }
    lines = []
    for key, (emoji, name) in labels.items():
        val = ratings.get(key, 0)
        bar = progress_bar(val, 100.0, 8)
        lines.append(f"`{bar}` **{val:.0f}** {emoji} {name}")
    return "\n".join(lines)


# ── Standard error messages ──────────────────────────────────────────────
ERR_DB = "❌ Error al conectar con la base de datos. Inténtalo más tarde."
ERR_JSON = "❌ Error al procesar los datos."
ERR_PLAYER_NOT_FOUND = "⚠️ Jugador '{}' no encontrado en la base de datos."
