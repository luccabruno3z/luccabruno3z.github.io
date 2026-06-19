"""Charts cog -- grafico, historial, and backward-compatible aliases."""

import logging
import os
import re
import json

import discord
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger(__name__)

from bot.config import (
    BOT_THUMBNAIL,
    graph_url,
    all_players_graph_url,
    GRAPH_ALIASES,
    CLAN_NAMES,
)
from bot.services.chart_renderer import render_history_chart
from bot.utils import format_number, standard_footer, find_player


def _safe_filename(filename: str) -> str:
    """Return a filesystem-safe version of *filename*."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", filename)


# ── Autocomplete helpers ───────────────────────────────────────────────────

async def clan_name_autocomplete(
    interaction: discord.Interaction, current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete for clan names."""
    options = ["all", "todos"] + CLAN_NAMES
    if current:
        filtered = [c for c in options if current.lower() in c.lower()]
    else:
        filtered = options
    return [app_commands.Choice(name=c, value=c) for c in filtered[:25]]


async def player_name_autocomplete(
    interaction: discord.Interaction, current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete for player names (for historial command)."""
    try:
        data = await interaction.client.data_fetcher.fetch_all_players()
    except Exception:
        return []
    names = [p["Player"] for p in data]
    if current:
        filtered = [n for n in names if current.lower() in n.lower()]
    else:
        filtered = names
    return [app_commands.Choice(name=n, value=n) for n in filtered[:25]]


def _clan_top_benchmark(all_players, clan, n=5, min_rounds=50):
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


class Charts(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Register backward-compatible aliases as commands
        for alias, clan in GRAPH_ALIASES.items():
            self._register_alias(alias, clan)

    # ── Dynamic alias registration ────────────────────────────────────────

    def _register_alias(self, alias: str, clan: str):
        """Create a command with *alias* that sends the graph link for *clan*."""

        async def _alias_callback(ctx: commands.Context):
            url = graph_url(clan)
            await ctx.send(
                f"[Aquí tienes el gráfico interactivo de {clan}!]({url})"
            )

        # Build a proper Command and attach it to the bot
        cmd = commands.Command(
            _alias_callback,
            name=alias,
            help=f"Gráfico interactivo de {clan}.",
        )
        cmd._buckets = commands.CooldownMapping.from_cooldown(
            1, 10, commands.BucketType.user,
        )
        cmd.cog = self
        self.bot.add_command(cmd)

    # ── -grafico <clan|all|todos> ─────────────────────────────────────────

    @commands.hybrid_command(name="grafico", aliases=["graph", "g"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    @app_commands.describe(clan="Nombre del clan (o 'all'/'todos' para todos)")
    @app_commands.autocomplete(clan=clan_name_autocomplete)
    async def grafico(self, ctx: commands.Context, clan: str = None):
        """Muestra el gráfico interactivo de un clan o de todos los jugadores."""
        if clan is None or clan.lower() in ("all", "todos"):
            url = all_players_graph_url()
            await ctx.send(
                f"[Aquí tienes el gráfico interactivo de los usuarios!]({url})"
            )
            return

        # Normalize: accept lowercase input
        clan_upper = clan.upper()
        if clan_upper not in CLAN_NAMES:
            valid = ", ".join(CLAN_NAMES)
            await ctx.send(
                f"❗ Clan '{clan}' no reconocido. Clanes válidos: {valid}, `all`/`todos`."
            )
            return

        url = graph_url(clan_upper)
        await ctx.send(
            f"[Aquí tienes el gráfico interactivo de {clan_upper}!]({url})"
        )

    # ── -historial <jugador> ──────────────────────────────────────────────

    @commands.hybrid_command(aliases=["hist", "history"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    @app_commands.describe(jugador="Nombre del jugador")
    @app_commands.autocomplete(jugador=player_name_autocomplete)
    async def historial(self, ctx: commands.Context, jugador: str = None):
        """Muestra un gráfico histórico del Performance Score de un jugador."""
        if not jugador:
            await ctx.send(
                "❗ Por favor, proporciona un nombre de jugador. "
                "Ejemplo: `-historial W4RR10R`."
            )
            return

        await ctx.defer()

        try:
            safe_name = _safe_filename(jugador)
            history_file = f"graphs/history/{safe_name}_history.json"

            if not os.path.exists(history_file):
                await ctx.send(
                    f"No se encontró historial de performance para el jugador {jugador}."
                )
                return

            with open(history_file, "r") as f:
                history_data = json.load(f)

            dates = [entry["Date"] for entry in history_data]
            scores = [entry["Performance Score"] for entry in history_data]
            # K/D por snapshot (None en los viejos que no lo guardaban → hueco en el grafico)
            kd_values = [entry.get("K/D Ratio") for entry in history_data]

            if len(scores) < 2:
                embed = discord.Embed(
                    title=f"📈 Historial de {jugador}",
                    description=(
                        f"Solo hay **{len(scores)}** registro(s) para **{jugador}**.\n"
                        "Se necesitan al menos **2 registros** para generar un grafico con tendencia.\n\n"
                        f"🌟 **Performance actual:** {format_number(scores[0]) if scores else 'N/A'}"
                    ),
                    color=discord.Color.orange(),
                )
                embed.set_thumbnail(url=BOT_THUMBNAIL)
                embed.set_footer(text=standard_footer())
                await ctx.send(embed=embed)
                return

            # Benchmark: promedio de los mejores del clan del jugador (best-effort).
            bench_ps = bench_kd = None
            try:
                all_players = await self.bot.data_fetcher.fetch_all_players()
                me = find_player(all_players, jugador) if isinstance(all_players, list) else None
                if me and me.get("Clan"):
                    bench_ps, bench_kd = _clan_top_benchmark(all_players, me["Clan"])
            except Exception:
                logger.debug("No se pudo calcular el benchmark de clan para %s", jugador)

            buf = render_history_chart(
                jugador, dates, scores, kd_values=kd_values,
                bench_ps=bench_ps, bench_kd=bench_kd,
            )
            file = discord.File(buf, filename=f"{safe_name}_history_chart.png")

            # Summary stats
            current = scores[-1]
            best = max(scores)
            worst = min(scores)
            trend = "📈 Mejorando" if len(scores) >= 2 and scores[-1] >= scores[-2] else "📉 Bajando"

            embed = discord.Embed(
                title=f"📈 Historial de {jugador}",
                description=(
                    f"Evolución del Performance Score a lo largo de **{len(scores)}** registros\n"
                    f"{trend} · Actual: **{format_number(current)}** · Mejor: **{format_number(best)}** · Peor: **{format_number(worst)}**"
                ),
                color=discord.Color.blue(),
            )
            embed.set_thumbnail(url=BOT_THUMBNAIL)
            embed.set_image(url=f"attachment://{safe_name}_history_chart.png")
            embed.set_footer(text=standard_footer())
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            await ctx.send("❗ Ocurrió un error inesperado. Intenta de nuevo más tarde.")
            logger.error("Error: %s", e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Charts(bot))
