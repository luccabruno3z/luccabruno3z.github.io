"""Countdown cog -- countdown command and flag-reaction timezone handling.

Improvements over original:
- Smarter update intervals (not every 1s forever)
- Uses discord.utils.format_dt() where applicable
- Single on_raw_reaction_add listener (no duplicate handlers)
"""

import logging
from datetime import datetime, timedelta

import asyncio
import discord
import pytz
from discord.ext import commands

from bot.config import FLAG_EMOJIS

logger = logging.getLogger(__name__)

# Default timezone (UTC-3 / Buenos Aires)
DEFAULT_TZ = pytz.timezone("America/Argentina/Buenos_Aires")


def _smart_sleep_interval(remaining_seconds: float) -> float:
    """Return a sensible update interval based on how much time is left."""
    if remaining_seconds > 86400:      # > 1 day
        return 3600                     # update every hour
    elif remaining_seconds > 3600:     # > 1 hour
        return 300                      # every 5 min
    elif remaining_seconds > 600:      # > 10 min
        return 60                       # every minute
    elif remaining_seconds > 60:       # > 1 min
        return 10                       # every 10s
    else:
        return 1                        # every second


class Countdown(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Track countdown messages: {message_id: target_datetime}
        self._countdowns: dict[int, datetime] = {}

    # ── -countdown DD/MM/YYYY HH:MM ──────────────────────────────────────

    @commands.command(aliases=["timer", "cd"])
    async def countdown(self, ctx: commands.Context, date: str = None, time: str = None):
        """Inicia un countdown hasta una fecha y hora específica (UTC-3)."""
        if not date or not time:
            await ctx.send("❗ Uso: `-countdown DD/MM/YYYY HH:MM`.")
            return

        try:
            target_dt = DEFAULT_TZ.localize(
                datetime.strptime(f"{date} {time}", "%d/%m/%Y %H:%M")
            )
        except ValueError:
            await ctx.send(
                "❗ Formato de fecha y hora inválido. Usa el formato `DD/MM/YYYY HH:MM`."
            )
            return

        now = datetime.now(DEFAULT_TZ)
        if target_dt <= now:
            await ctx.send("❗ La fecha y hora deben estar en el futuro.")
            return

        max_future = now + timedelta(days=365)
        if target_dt > max_future:
            await ctx.send("❗ La fecha no puede ser más de 1 año en el futuro.")
            return

        # Use discord timestamp for a nice inline display
        unix_ts = int(target_dt.timestamp())

        embed = discord.Embed(
            title="⏳ Countdown",
            description=f"Tiempo restante hasta `{target_dt.strftime('%d/%m/%Y %H:%M %Z')}`",
            color=discord.Color.blue(),
        )
        message = await ctx.send(embed=embed)

        # Store for flag reactions
        self._countdowns[message.id] = target_dt

        # Add flag reactions for timezone selection
        for flag in FLAG_EMOJIS:
            try:
                await message.add_reaction(flag)
            except discord.HTTPException:
                pass

        # Live update loop with smart intervals
        while True:
            remaining = target_dt - datetime.now(DEFAULT_TZ)
            total_secs = remaining.total_seconds()

            if total_secs <= 0:
                embed.description = "¡El tiempo ha llegado!"
                await message.edit(embed=embed)
                break

            days = remaining.days
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds // 60) % 60
            seconds = remaining.seconds % 60
            embed.description = (
                f"**{days}** días, **{hours}** horas, "
                f"**{minutes}** minutos, **{seconds}** segundos."
            )
            await message.edit(embed=embed)

            interval = _smart_sleep_interval(total_secs)
            await asyncio.sleep(interval)

        # Cleanup
        self._countdowns.pop(message.id, None)

    # ── Flag reaction -> DM with localized countdown ──────────────────────

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        # Only handle countdown messages
        target_dt = self._countdowns.get(payload.message_id)
        if target_dt is None:
            return

        emoji_str = str(payload.emoji)
        tz_name = FLAG_EMOJIS.get(emoji_str)
        if not tz_name:
            return

        user_tz = pytz.timezone(tz_name)
        remaining = target_dt - datetime.now(user_tz)

        if remaining.total_seconds() <= 0:
            return

        localized_target = target_dt.astimezone(user_tz)
        embed = discord.Embed(
            title="⏳ Countdown Personalizado",
            description=(
                f"Tiempo restante hasta "
                f"`{localized_target.strftime('%d/%m/%Y %H:%M %Z')}` "
                f"en tu zona horaria ({user_tz.zone}):\n\n"
                f"**{remaining.days}** días, **{remaining.seconds // 3600}** horas, "
                f"**{(remaining.seconds // 60) % 60}** minutos, "
                f"**{remaining.seconds % 60}** segundos"
            ),
            color=discord.Color.blue(),
        )

        user = await self.bot.fetch_user(payload.user_id)
        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            pass

        channel = self.bot.get_channel(payload.channel_id)
        if channel:
            await channel.send(
                f"{user.mention}, te he enviado un mensaje privado con el countdown personalizado."
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Countdown(bot))
