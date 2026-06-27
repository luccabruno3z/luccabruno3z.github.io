"""Misc cog -- ayuda, hola, guias, visualizador, pagina, apagar, on_ready, on_command_error."""

import logging
import os

import discord
from discord.ext import commands
from discord import app_commands

from bot.config import GITHUB_INDEX, GITHUB_GUIDES, GITHUB_VISUALIZER_2D, BOT_THUMBNAIL
from bot.views.mode_selector import ModeSelectorView

logger = logging.getLogger(__name__)


class Misc(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._synced = False
        self._emojis_synced = False

    # ── on_ready ──────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_ready(self):
        if not self._synced:
            await self.bot.tree.sync()
            self._synced = True
            logger.info("Slash commands sincronizados.")
        if not self._emojis_synced:
            try:
                await self._sync_app_emojis()
                self._emojis_synced = True
            except Exception as exc:
                logger.warning("No se pudieron sincronizar los app emojis: %s", exc)
        logger.info("Bot conectado como %s", self.bot.user)

    async def _sync_app_emojis(self):
        """Repuebla los caches de emojis (kit/vehículo/rango/clan) desde los Application
        Emojis ya subidos a Discord. El disco de Railway es efímero → sin esto, tras cada
        redeploy se pierde el mapeo nombre→id y desaparecen los iconos hasta re-correr
        -setup_emojis. Acá se reconstruye solo al arrancar (los emojis siguen en Discord)."""
        from bot.assets.kit_mapping import update_emoji_cache
        from bot.assets.rank_mapping import update_rank_emoji_cache, get_all_rank_assets
        from bot.assets.clan_mapping import update_clan_emoji_cache, get_all_clan_assets
        rank_names = {n for n, _ in get_all_rank_assets()}
        clan_names = {n for n, _ in get_all_clan_assets()}
        emojis = await self.bot.fetch_application_emojis()
        for e in emojis:
            token = f"<{'a' if e.animated else ''}:{e.name}:{e.id}>"
            if e.name in rank_names:
                update_rank_emoji_cache(e.name, token)
            elif e.name in clan_names:
                update_clan_emoji_cache(e.name, token)
            else:
                update_emoji_cache(e.name, token)
        logger.info("App emojis sincronizados desde Discord: %d", len(emojis))

    # ── on_command_error ──────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        error = getattr(error, "original", error)

        if isinstance(error, commands.CommandNotFound):
            await ctx.send(
                "❌ **Comando no reconocido.** Usa `-ayuda` para ver todos los comandos."
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                "❗ Faltan argumentos. Usa `-ayuda` para ver el uso correcto."
            )
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("🚫 No tienes permisos para ejecutar este comando.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("⚠️ Argumento inválido. Revisa los parámetros del comando.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏳ Cooldown activo. Intenta en {error.retry_after:.1f}s."
            )
        else:
            await ctx.send("❗ Ocurrió un error inesperado. Intenta de nuevo más tarde.")
            logger.error("Error inesperado: %s", error)

    # ── -hola / -hi ─────────────────────────────────────────────────────

    @commands.command(aliases=["hi", "hello"])
    async def hola(self, ctx: commands.Context):
        await ctx.send("¡Hola! ¿En qué puedo ayudarte? Usa `-ayuda` para ver todos los comandos.")

    # ── -guias / -guides ─────────────────────────────────────────────────

    @commands.command(aliases=["guides"])
    async def guias(self, ctx: commands.Context):
        await ctx.send(f"[Aquí tienes acceso a las guías de la página!]({GITHUB_GUIDES})")

    # ── -visualizador / -vis / -2d ───────────────────────────────────────

    @commands.command(aliases=["vis", "2d"])
    async def visualizador(self, ctx: commands.Context):
        await ctx.send(f"[Aquí tienes acceso al visualizador 2D!]({GITHUB_VISUALIZER_2D})")

    # ── -pagina / -web / -page ───────────────────────────────────────────

    @commands.command(aliases=["web", "page"])
    async def pagina(self, ctx: commands.Context):
        await ctx.send(f"[Aquí tienes la pagina de la LDH!]({GITHUB_INDEX})")

    # ── -apagar / -shutdown ──────────────────────────────────────────────

    @commands.command(aliases=["shutdown"])
    @commands.is_owner()
    async def apagar(self, ctx: commands.Context):
        await ctx.send("🔌 Apagando el bot...")
        await self.bot.close()

    # ── -setup_emojis ────────────────────────────────────────────────────

    @commands.command()
    @commands.is_owner()
    async def setup_emojis(self, ctx: commands.Context):
        """Sube los iconos de kits y rangos como Application Emojis del bot."""
        import aiohttp, base64, asyncio
        from bot.assets.kit_mapping import get_all_assets, update_emoji_cache
        from bot.assets.rank_mapping import get_all_rank_assets, update_rank_emoji_cache
        from bot.assets.clan_mapping import get_all_clan_assets, update_clan_emoji_cache
        from bot.assets.vehicle_mapping import get_all_vehicle_assets

        # Combine kit + rank + clan + vehicle assets
        kit_assets = get_all_assets()
        rank_assets = get_all_rank_assets()
        clan_assets = get_all_clan_assets()
        vehicle_assets = get_all_vehicle_assets()
        assets = kit_assets + rank_assets + clan_assets + vehicle_assets
        # Track which names belong to which cache (vehículos van al cache de kits).
        rank_names = {name for name, _ in rank_assets}
        clan_names = {name for name, _ in clan_assets}
        if not assets:
            await ctx.send("No se encontraron assets para subir.")
            return

        token = os.getenv("DISCORD_TOKEN")
        app_id = self.bot.application_id or self.bot.user.id

        status = await ctx.send(f"Subiendo {len(assets)} emojis como Application Emojis...")

        # Fetch existing application emojis
        headers = {"Authorization": f"Bot {token}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://discord.com/api/v10/applications/{app_id}/emojis",
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    existing = {e["name"]: e for e in data.get("items", [])}
                else:
                    existing = {}
                    logger.warning("Failed to fetch app emojis: %s", resp.status)

            uploaded = 0
            skipped = 0
            failed = 0

            def _save_emoji(name, emoji_str):
                """Save to the correct cache (kit / rank / clan)."""
                if name in rank_names:
                    update_rank_emoji_cache(name, emoji_str)
                elif name in clan_names:
                    update_clan_emoji_cache(name, emoji_str)
                else:
                    update_emoji_cache(name, emoji_str)

            def _emoji_str(e):
                """Build the inline emoji token, animated-aware (<a:..> for gifs)."""
                prefix = "a" if e.get("animated") else ""
                return f"<{prefix}:{e['name']}:{e['id']}>"

            for emoji_name, path in assets:
                if emoji_name in existing:
                    e = existing[emoji_name]
                    _save_emoji(emoji_name, _emoji_str(e))
                    skipped += 1
                    continue

                try:
                    with open(path, "rb") as f:
                        img_data = f.read()
                    b64 = base64.b64encode(img_data).decode("utf-8")
                    mime = "image/gif" if path.lower().endswith(".gif") else "image/png"
                    payload = {
                        "name": emoji_name,
                        "image": f"data:{mime};base64,{b64}",
                    }
                    # Reintenta ante 429 (rate limit) respetando Retry-After. Muchos
                    # iconos de vehículo → conviene no fallar por rate limit.
                    for _attempt in range(5):
                        async with session.post(
                            f"https://discord.com/api/v10/applications/{app_id}/emojis",
                            headers={**headers, "Content-Type": "application/json"},
                            json=payload,
                        ) as resp:
                            if resp.status in (200, 201):
                                e = await resp.json()
                                _save_emoji(emoji_name, _emoji_str(e))
                                uploaded += 1
                                break
                            if resp.status == 429:
                                retry = 1.0
                                try:
                                    retry = float((await resp.json()).get("retry_after", 1.0))
                                except Exception:
                                    pass
                                await asyncio.sleep(min(retry + 0.25, 10))
                                continue
                            body = await resp.text()
                            logger.warning("Failed to upload app emoji %s: %s %s", emoji_name, resp.status, body)
                            failed += 1
                            break
                    else:
                        failed += 1
                except Exception as exc:
                    logger.warning("Failed to upload app emoji %s: %s", emoji_name, exc)
                    failed += 1

        await status.edit(
            content=f"✅ Application Emojis: **{uploaded}** subidos, **{skipped}** ya existían, **{failed}** fallaron."
        )

    @commands.hybrid_command(name="ayuda", aliases=["comandos", "commands", "h"])
    async def ayuda(self, ctx: commands.Context):
        """Lista todos los comandos del bot, agrupados por categoría."""
        from bot.ui.help_view import HelpView
        await ctx.send(view=HelpView(self.bot))

    @commands.hybrid_command(name="glosario", aliases=["glossary", "terminos", "términos"])
    @app_commands.describe(categoria="basicas / performance / indices / radar / arquetipos / otros")
    async def glosario(self, ctx: commands.Context, categoria: str = "basicas"):
        """Explica qué significa cada término (K/D, Índice Táctico, tiers...) y de dónde sale."""
        from bot.ui.glossary import GlossaryView, GLOSSARY
        cat = categoria.lower() if categoria.lower() in GLOSSARY else "basicas"
        await ctx.send(view=GlossaryView(cat))

    @commands.hybrid_command(name="modo", aliases=["mode", "datos"])
    async def modo(self, ctx: commands.Context):
        """Muestra y cambia el modo de datos del servidor (PRStats / Demos / Combinado)."""
        mode_view = ModeSelectorView(self.bot.guild_settings, ctx.guild.id if ctx.guild else 0)
        mode_view.message = await ctx.send("📡 Elegí el modo de datos del servidor:", view=mode_view)

    # ── Redirect -help to -ayuda (separate command to avoid conflict) ────

    @commands.command(name="help", hidden=True)
    async def help_redirect(self, ctx: commands.Context):
        await self.ayuda(ctx)


async def setup(bot: commands.Bot):
    await bot.add_cog(Misc(bot))
