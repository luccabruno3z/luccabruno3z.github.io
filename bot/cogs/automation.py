"""Background tasks: leaderboard automático, cache refresh, player of the week."""

import datetime
import logging

import discord
from discord.ext import commands, tasks

from bot.config import CLAN_EMOJIS
from bot.assets.clan_mapping import get_clan_emoji
from bot.services.storage import JSONStorage

logger = logging.getLogger(__name__)

# Hora del leaderboard semanal (lunes). Con un loop por intervalo (hours=168) se
# disparaba en cada arranque, o sea en cada redeploy.
LEADERBOARD_TIME = datetime.time(hour=10, minute=0, tzinfo=datetime.timezone.utc)
LEADERBOARD_WEEKDAY = 0  # lunes


class Automation(commands.Cog):
    """Automated background tasks for the LDH stats bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.fetcher = bot.data_fetcher
        # Archivo propio: guild_settings.json es de GuildSettings (modos de datos).
        self.settings = JSONStorage("automation.json")

    async def cog_load(self):
        self.cache_refresh.start()
        self.weekly_leaderboard.start()
        logger.info("Automation tasks started.")

    async def cog_unload(self):
        self.cache_refresh.cancel()
        self.weekly_leaderboard.cancel()

    # ── Cache refresh every 5 minutes ──────────────────────────────────────

    @tasks.loop(minutes=5)
    async def cache_refresh(self):
        """Pre-fetch common data to keep cache warm."""
        try:
            await self.fetcher.pre_cache()
        except Exception as e:
            logger.warning("Cache refresh failed: %s", e)
        # Una vez por hora, los nombres legibles de assets (el scraper suma armas,
        # vehículos y mapas nuevos; antes solo se cargaban al arrancar).
        if self.cache_refresh.current_loop % 12 == 11:
            try:
                from bot.assets.kit_mapping import load_aliases
                await load_aliases()
            except Exception as e:
                logger.warning("Alias refresh failed: %s", e)

    @cache_refresh.before_loop
    async def before_cache_refresh(self):
        await self.bot.wait_until_ready()

    # ── Weekly leaderboard (every Monday at 10:00 UTC) ─────────────────────

    @tasks.loop(time=LEADERBOARD_TIME)  # corre a diario; solo publica los lunes
    async def weekly_leaderboard(self):
        """Post top 10 players in configured channels."""
        if datetime.datetime.now(datetime.timezone.utc).weekday() != LEADERBOARD_WEEKDAY:
            return
        # Un error no manejado dentro de un tasks.loop lo detiene para siempre (hasta el
        # próximo reinicio): todo el cuerpo va protegido.
        try:
            await self._post_weekly_leaderboard()
        except Exception:
            logger.exception("Weekly leaderboard failed")

    async def _post_weekly_leaderboard(self):
        try:
            data = await self.fetcher.fetch_all_players()
        except Exception as e:
            logger.error("Weekly leaderboard fetch failed: %s", e)
            return
        if not isinstance(data, list) or not data:
            logger.error("Weekly leaderboard: all_players vacío o con formato inesperado.")
            return

        sorted_players = sorted(data, key=lambda x: x.get("Performance Score", 0), reverse=True)
        top10 = sorted_players[:10]

        embed = discord.Embed(
            title="🏆 **Top 10 Semanal — Performance Score**",
            description="Ranking actualizado automáticamente:",
            color=discord.Color.gold(),
        )

        ranking_text = ""
        for i, p in enumerate(top10, 1):
            clan = p.get("Clan", "")
            emoji = get_clan_emoji(clan)
            name = p.get("Player", "???")
            score = p.get("Performance Score", 0)
            ranking_text += f"**#{i}** {emoji} {name} — {score:.2f}\n"

        embed.add_field(name="🔝 Ranking", value=ranking_text, inline=False)
        embed.set_footer(text="Actualizado automáticamente cada semana.")

        # Post to all configured channels
        for guild_id, config in self.settings.all().items():
            channel_id = config.get("leaderboard_channel") if isinstance(config, dict) else None
            if not channel_id:
                continue
            channel = self.bot.get_channel(int(channel_id))
            if channel:
                try:
                    await channel.send(embed=embed)
                    logger.info("Leaderboard posted in guild %s", guild_id)
                except discord.Forbidden:
                    logger.warning("No permission to post in channel %s", channel_id)
                except discord.HTTPException as e:
                    # Un canal con problemas no corta el envío a los demás.
                    logger.warning("Could not post leaderboard in channel %s: %s", channel_id, e)

    @weekly_leaderboard.before_loop
    async def before_weekly_leaderboard(self):
        await self.bot.wait_until_ready()

    # ── Admin commands ─────────────────────────────────────────────────────

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def set_leaderboard_channel(self, ctx, channel: discord.TextChannel):
        """Configura el canal para el leaderboard automático semanal."""
        guild_config = self.settings.get(str(ctx.guild.id), {})
        guild_config["leaderboard_channel"] = channel.id
        self.settings.set(str(ctx.guild.id), guild_config)
        await ctx.send(f"✅ Leaderboard semanal configurado en {channel.mention}")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def remove_leaderboard_channel(self, ctx):
        """Desactiva el leaderboard automático."""
        guild_config = self.settings.get(str(ctx.guild.id), {})
        guild_config.pop("leaderboard_channel", None)
        self.settings.set(str(ctx.guild.id), guild_config)
        await ctx.send("✅ Leaderboard semanal desactivado.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Automation(bot))
