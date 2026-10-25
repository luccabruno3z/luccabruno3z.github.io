"""Menu cog — -menu (hub navegable) y -vincular / -desvincular."""

import logging

from discord import app_commands
from discord.ext import commands

from bot.cogs.stats import player_name_autocomplete
from bot.services import links
from bot.ui.menu import build_menu
from bot.utils import find_player

logger = logging.getLogger(__name__)


class Menu(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="menu", aliases=["inicio", "hub"])
    async def menu(self, ctx: commands.Context):
        """Menú navegable con todas las secciones del bot (perfil, rankings, clanes…)."""
        await ctx.defer()
        view = await build_menu(self.bot, "home", ctx.author.id)
        await ctx.send(view=view)

    @commands.hybrid_command(name="vincular", aliases=["link", "soy"])
    @app_commands.describe(jugador="Tu nombre de jugador en Project Reality")
    @app_commands.autocomplete(jugador=player_name_autocomplete)
    async def vincular(self, ctx: commands.Context, *, jugador: str = None):
        """Vincula tu cuenta de Discord con tu jugador (lo usa -menu en «Mi perfil»)."""
        if not jugador:
            actual = links.get(ctx.author.id)
            msg = (f"Estás vinculado como **{actual}**. Cambialo con `-vincular <ign>` "
                   f"o borralo con `-desvincular`." if actual else
                   "Usá `-vincular <ign>`, por ejemplo `-vincular W4RR10R`.")
            await ctx.send(msg, ephemeral=True)
            return
        await ctx.defer(ephemeral=True)
        try:
            data = await self.bot.data_fetcher.fetch_all_players()
            p = find_player(data, jugador)
        except Exception as exc:
            logger.warning("vincular: no se pudo validar %s: %s", jugador, exc)
            p = None
        if not p:
            await ctx.send(f"No encontré a **{jugador}** en PRStats. Revisá el nombre con `-buscar`.",
                           ephemeral=True)
            return
        links.set(ctx.author.id, p["Player"])
        await ctx.send(f"✅ Listo: quedaste vinculado como **{p['Player']}**. Probá `-menu` → Mi perfil.",
                       ephemeral=True)

    @commands.hybrid_command(name="desvincular", aliases=["unlink"])
    async def desvincular(self, ctx: commands.Context):
        """Borra el vínculo entre tu cuenta de Discord y tu jugador."""
        links.delete(ctx.author.id)
        await ctx.send("Listo, ya no estás vinculado a ningún jugador.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Menu(bot))
