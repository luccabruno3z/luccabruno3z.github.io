"""Bot entrypoint. Run as `python bot/main.py` or `python -m bot`."""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
import discord
from discord.ext import commands

from bot.config import COMMAND_PREFIX
from bot.services.clan_registry import ClanRegistry
from bot.services.data_fetcher import DataFetcher
from bot.services.guild_settings import GuildSettings

# Logging a stdout para que se vea en `railway logs` (sin esto, Python solo emite
# WARNING+). Nivel configurable con LOG_LEVEL (default INFO); discord en WARNING para
# no spamear el heartbeat/gateway.
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger("discord").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# ── Cogs to load ──────────────────────────────────────────────────────────────
EXTENSIONS = [
    "bot.cogs.stats",
    "bot.cogs.charts",
    "bot.cogs.compare",
    "bot.cogs.tips",
    "bot.cogs.roles",
    "bot.cogs.countdown",
    "bot.cogs.misc",
    "bot.cogs.automation",
    "bot.cogs.detailed_stats",
    "bot.cogs.polls",
    "bot.cogs.suggestions",
]


async def main():
    # Load .env if present (local dev)
    if os.path.exists(".env"):
        load_dotenv()

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("El token del bot no está definido en las variables de entorno")
    logger.info("Token detectado correctamente")

    # Configure intents (NOT all() -- only what we need)
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.reactions = True

    # Make slash commands user-installable and usable in DMs / any server,
    # not just guilds where the bot is added (discord.py 2.4+).
    bot = commands.Bot(
        command_prefix=COMMAND_PREFIX,
        intents=intents,
        allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True),
        allowed_contexts=discord.app_commands.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True
        ),
    )

    # Disable the built-in help so our custom -ayuda works without conflict
    bot.remove_command("help")

    # Initialize the shared data fetcher and attach it to the bot
    bot.data_fetcher = DataFetcher(ttl=300, timeout=10)

    # Initialize guild settings (data mode per server)
    bot.guild_settings = GuildSettings()

    # Load emoji caches (kits + ranks)
    from bot.assets.kit_mapping import load_emoji_cache, load_aliases
    from bot.assets.rank_mapping import load_rank_emoji_cache
    from bot.assets.clan_mapping import load_clan_emoji_cache
    load_emoji_cache()
    load_rank_emoji_cache()
    load_clan_emoji_cache()
    # Humanized asset aliases (kits/weapons/vehicles/maps) shared with the web.
    await load_aliases()

    # Registro de clanes data-driven (bot.clans). Se baja clan_averages.json y de ahí
    # salen categorías de -top, autocompletes, URLs por clan y atajos -grafico<clan>.
    # DEBE quedar listo ANTES de load_extension: el cog Charts registra los atajos en
    # su setup. Fallback a la lista bundled si el fetch falla (arranque offline).
    try:
        averages = await bot.data_fetcher.fetch_clan_averages()
        bot.clans = ClanRegistry.from_averages(averages)
    except Exception as exc:
        logger.warning("No se pudo derivar clanes de clan_averages.json (%s); uso fallback.", exc)
        bot.clans = ClanRegistry.from_averages(None)
    logger.info("Clan registry: %d clanes (%s)", len(bot.clans.tags), ", ".join(bot.clans.tags))

    # Load all cogs
    for ext in EXTENSIONS:
        await bot.load_extension(ext)
        logger.info("  Cog cargado: %s", ext)

    # Register persistent (DynamicItem) components so player-card buttons keep
    # working across restarts/redeploys instead of going dead.
    from bot.ui.player_card_actions import PlayerCardActionButton
    bot.add_dynamic_items(PlayerCardActionButton)
    logger.info("  DynamicItems registrados: PlayerCardActionButton")

    # Run the bot; ensure clean shutdown of aiohttp session
    try:
        await bot.start(token)
    finally:
        await bot.data_fetcher.close()


if __name__ == "__main__":
    asyncio.run(main())
