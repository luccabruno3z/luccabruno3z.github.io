"""Charts cog -- grafico, historial, and backward-compatible aliases."""

import logging

import discord
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger(__name__)

from bot.config import (
    graph_url,
    all_players_graph_url,
    GRAPH_ALIASES,
    CLAN_NAMES,
)
from bot.services.history_chart import build_history_embed


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
            embed, file = await build_history_embed(self.bot.data_fetcher, jugador)
            if file:
                await ctx.send(embed=embed, file=file)
            else:
                await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send("❗ Ocurrió un error inesperado. Intenta de nuevo más tarde.")
            logger.error("Error: %s", e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Charts(bot))
