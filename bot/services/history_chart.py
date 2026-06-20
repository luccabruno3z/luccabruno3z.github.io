"""Constructor unificado del gráfico de historial.

Fuente única para `-historial`, el botón "Historial" de la player card y la
StatsView. Garantiza que los tres usen:
  - la **misma búsqueda** de jugador (`find_player`: exacta → case-insensitive → parcial),
  - la **misma fuente** de datos (HTTP fresco desde GitHub Pages, no el archivo local
    que queda viejo entre deploys),
  - el **mismo gráfico** completo (Performance Score + K/D + líneas de referencia del
    top del clan).
"""

from __future__ import annotations

import logging
import re

import discord

from bot.config import BASE_URL, BOT_THUMBNAIL
from bot.services.chart_renderer import render_history_chart
from bot.utils import find_player, format_number, standard_footer

logger = logging.getLogger(__name__)


def safe_filename(name: str) -> str:
    """Versión filesystem-safe de un nombre (debe espejar scraper/history.py)."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", name)


def clan_top_benchmark(all_players, clan, n=5, min_rounds=50):
    """Promedio de PS y K/D de los mejores `n` jugadores del clan (por Performance
    Score, calificados con >= min_rounds). Devuelve (ps, kd) o (None, None)."""
    if not isinstance(all_players, list) or not clan:
        return None, None
    members = [p for p in all_players if p.get("Clan") == clan]
    if not members:
        return None, None
    qualified = [p for p in members if (p.get("Rounds", 0) or 0) >= min_rounds] or members
    top = sorted(qualified, key=lambda p: p.get("Performance Score", 0) or 0, reverse=True)[:n]
    if not top:
        return None, None
    ps = sum((p.get("Performance Score", 0) or 0) for p in top) / len(top)
    kd = sum((p.get("K/D Ratio", 0) or 0) for p in top) / len(top)
    return round(ps, 4), round(kd, 2)


async def build_history_embed(data_fetcher, jugador, *, color=None):
    """Resuelve el jugador, baja su historial y arma el gráfico completo.

    Devuelve `(embed, file)`. `file` es `None` cuando no hay datos suficientes
    (el embed explica el motivo). El caller solo tiene que mandarlos.
    """
    # 1. Resolver el nombre (búsqueda uniforme con el resto de comandos).
    all_players = None
    try:
        all_players = await data_fetcher.fetch_all_players()
    except Exception:
        logger.debug("No se pudo bajar all_players para resolver %s", jugador)
    player = find_player(all_players, jugador) if isinstance(all_players, list) else None
    actual_name = player["Player"] if player else jugador

    # 2. Bajar el historial fresco vía HTTP (el archivo local queda viejo entre deploys).
    url = f"{BASE_URL}/graphs/history/{safe_filename(actual_name)}_history.json"
    try:
        history_data = await data_fetcher.fetch_json(url, use_stale_on_error=False)
    except Exception:
        history_data = None

    if not isinstance(history_data, list) or not history_data:
        return _info_embed(
            actual_name,
            f"No se encontró historial de performance para **{actual_name}**.\n"
            "*El historial se genera cada hora.*",
        ), None

    dates = [e.get("Date", e.get("date", "?")) for e in history_data]
    scores = [e.get("Performance Score", 0) for e in history_data]
    # K/D por snapshot (None en los viejos que no lo guardaban → hueco en el gráfico).
    kd_values = [e.get("K/D Ratio") for e in history_data]

    if len(scores) < 2:
        return _info_embed(
            actual_name,
            f"Solo hay **{len(scores)}** registro(s) para **{actual_name}**.\n"
            "Se necesitan al menos **2 registros** para generar un gráfico con tendencia.\n\n"
            f"🌟 **Performance actual:** {format_number(scores[0]) if scores else 'N/A'}",
        ), None

    # 3. Benchmark del top del clan (best-effort).
    bench_ps = bench_kd = None
    if player and player.get("Clan") and isinstance(all_players, list):
        try:
            bench_ps, bench_kd = clan_top_benchmark(all_players, player["Clan"])
        except Exception:
            logger.debug("No se pudo calcular el benchmark de clan para %s", actual_name)

    buf = render_history_chart(
        actual_name, dates, scores, kd_values=kd_values,
        bench_ps=bench_ps, bench_kd=bench_kd,
    )
    filename = f"{safe_filename(actual_name)}_history_chart.png"
    file = discord.File(buf, filename=filename)

    current = scores[-1]
    best = max(scores)
    worst = min(scores)
    trend = "📈 Mejorando" if scores[-1] >= scores[-2] else "📉 Bajando"

    embed = discord.Embed(
        title=f"📈 Historial de {actual_name}",
        description=(
            f"Evolución del Performance Score a lo largo de **{len(scores)}** registros\n"
            f"{trend} · Actual: **{format_number(current)}** · "
            f"Mejor: **{format_number(best)}** · Peor: **{format_number(worst)}**"
        ),
        color=color or discord.Color.blue(),
    )
    embed.set_thumbnail(url=BOT_THUMBNAIL)
    embed.set_image(url=f"attachment://{filename}")
    embed.set_footer(text=standard_footer())
    return embed, file


def _info_embed(name, description):
    embed = discord.Embed(
        title=f"📈 Historial de {name}",
        description=description,
        color=discord.Color.orange(),
    )
    embed.set_thumbnail(url=BOT_THUMBNAIL)
    embed.set_footer(text=standard_footer())
    return embed
