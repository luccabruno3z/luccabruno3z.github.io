"""Misc cog -- ayuda, hola, guias, visualizador, pagina, apagar, on_ready, on_command_error."""

import logging
import os

import discord
from discord.ext import commands

from bot.config import GITHUB_INDEX, GITHUB_GUIDES, GITHUB_VISUALIZER_2D, BOT_THUMBNAIL
from bot.views.mode_selector import ModeSelectorView

logger = logging.getLogger(__name__)


class Misc(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._synced = False

    # ── on_ready ──────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_ready(self):
        if not self._synced:
            await self.bot.tree.sync()
            self._synced = True
            logger.info("Slash commands sincronizados.")
        logger.info("Bot conectado como %s", self.bot.user)

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
        import aiohttp, base64
        from bot.assets.kit_mapping import get_all_assets, update_emoji_cache
        from bot.assets.rank_mapping import get_all_rank_assets, update_rank_emoji_cache

        # Combine kit + rank assets
        kit_assets = get_all_assets()
        rank_assets = get_all_rank_assets()
        assets = kit_assets + rank_assets
        # Track which are ranks for correct cache update
        rank_names = {name for name, _ in rank_assets}
        if not assets:
            await ctx.send("No se encontraron assets de kits.")
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
                """Save to correct cache (kit or rank)."""
                if name in rank_names:
                    update_rank_emoji_cache(name, emoji_str)
                else:
                    update_emoji_cache(name, emoji_str)

            for emoji_name, path in assets:
                if emoji_name in existing:
                    e = existing[emoji_name]
                    emoji_str = f"<:{e['name']}:{e['id']}>"
                    _save_emoji(emoji_name, emoji_str)
                    skipped += 1
                    continue

                try:
                    with open(path, "rb") as f:
                        img_data = f.read()
                    b64 = base64.b64encode(img_data).decode("utf-8")
                    payload = {
                        "name": emoji_name,
                        "image": f"data:image/png;base64,{b64}",
                    }
                    async with session.post(
                        f"https://discord.com/api/v10/applications/{app_id}/emojis",
                        headers={**headers, "Content-Type": "application/json"},
                        json=payload,
                    ) as resp:
                        if resp.status in (200, 201):
                            e = await resp.json()
                            emoji_str = f"<:{e['name']}:{e['id']}>"
                            _save_emoji(emoji_name, emoji_str)
                            uploaded += 1
                        else:
                            body = await resp.text()
                            logger.warning("Failed to upload app emoji %s: %s %s", emoji_name, resp.status, body)
                            failed += 1
                except Exception as exc:
                    logger.warning("Failed to upload app emoji %s: %s", emoji_name, exc)
                    failed += 1

        await status.edit(
            content=f"✅ Application Emojis: **{uploaded}** subidos, **{skipped}** ya existían, **{failed}** fallaron."
        )

    # ── -ayuda / -help / -comandos / -commands ───────────────────────────

    @commands.command(aliases=["comandos", "commands", "h"])
    async def ayuda(self, ctx: commands.Context):
        from bot.views.pagination import PaginationView

        COLOR = discord.Color.from_rgb(0, 255, 255)  # Cyan LDH

        # ─── Page 1: Bienvenida + Stats personales ───────────────────────
        e1 = discord.Embed(
            title="🎖️ LDH Stats Bot — Centro de Comandos",
            description=(
                "Tu herramienta para analizar, comparar y mejorar\n"
                "en **Project Reality**. Usá `-` o `/` como prefijo.\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=COLOR,
        )
        e1.set_thumbnail(url=BOT_THUMBNAIL)

        e1.add_field(
            name="📊 Tu Perfil y Estadísticas",
            value=(
                "```\n"
                "-stats <jugador>    Ver stats completas\n"
                "-perfil <jugador>   Radar + estilo de juego\n"
                "-historial <jugador> Gráfico de evolución\n"
                "-tendencia <jugador> Análisis de tendencia\n"
                "-mejora <jugador>   Plan de mejora personal\n"
                "```"
            ),
            inline=False,
        )

        e1.add_field(
            name="🔍 Buscar Jugadores",
            value=(
                "```\n"
                "-buscar <nombre>    Buscar por nombre parcial\n"
                "```"
            ),
            inline=False,
        )

        e1.add_field(
            name="💡 Aliases rápidos",
            value=(
                "`-stats` = `-estadisticas` = `-st`\n"
                "`-p` = `-perfil` = `-profile`\n"
                "`-hist` = `-historial` · `-trend` = `-tendencia`\n"
                "`-improve` = `-mejora` = `-goals`\n"
                "`-search` = `-buscar` = `-find`"
            ),
            inline=False,
        )

        # ─── Page 2: Comparaciones + Equipos ─────────────────────────────
        e2 = discord.Embed(
            title="⚔️ Comparaciones y Equipos",
            description="Medite contra otros y armá el mejor equipo.\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=COLOR,
        )
        e2.set_thumbnail(url=BOT_THUMBNAIL)

        e2.add_field(
            name="🆚 Comparar",
            value=(
                "```\n"
                "-vs <j1> <j2>       Jugador vs Jugador\n"
                "-vs <clan1> <clan2>  Clan vs Clan\n"
                "-compare_tops <c1> <c2> [N]\n"
                "  Top N de un clan vs otro\n"
                "-predict <E1> vs <E2> Predicción de partida\n"
                "```"
            ),
            inline=False,
        )

        e2.add_field(
            name="👥 Equipos",
            value=(
                "```\n"
                "-team <j1 j2 ...>   Analizar equipo (2-8)\n"
                "-suggest <clan> <N> Sugerir mejor equipo\n"
                "-teamvs <E1> <E2> <jugadores>\n"
                "                    Comparar dos equipos\n"
                "```"
            ),
            inline=False,
        )

        e2.add_field(
            name="💡 Aliases rápidos",
            value=(
                "`-vs` = `-compare` = `-comp`\n"
                "`-compare_tops` = `-tops` = `-topvs`\n"
                "`-team` = `-analizar_equipo` = `-equipo`\n"
                "`-suggest` = `-sugerir_equipo`\n"
                "`-predict` = `-prediccion` = `-pred`"
            ),
            inline=False,
        )

        # ─── Page 3: Rankings ─────────────────────────────────────────────
        e3 = discord.Embed(
            title="🏆 Rankings y Promedios",
            description="Leaderboards y estadísticas de clanes.\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=COLOR,
        )
        e3.set_thumbnail(url=BOT_THUMBNAIL)

        e3.add_field(
            name="🏅 Rankings",
            value=(
                "```\n"
                "-top <N> <cat> <métrica>\n"
                "  Top jugadores con paginación\n"
                "  Categorías: general, ldh, sae,\n"
                "    fi, 141, fi-r, r-ldh, e-lam,\n"
                "    300, rim-la, adg, faso, porn, a-ldh\n"
                "  Métricas: performance, kd, kills,\n"
                "    deaths, rounds\n"
                "\n"
                "-weekly             Top mejoras semanales\n"
                "```"
            ),
            inline=False,
        )

        e3.add_field(
            name="📊 Promedios de Clanes",
            value=(
                "```\n"
                "-avg                Promedios por clan\n"
                "-avgtop <N> <métrica>\n"
                "  Promedios de los mejores N\n"
                "```"
            ),
            inline=False,
        )

        e3.add_field(
            name="💡 Aliases rápidos",
            value=(
                "`-ranking` = `-top` = `-lb` = `-leaderboard`\n"
                "`-weekly` = `-ranking_semanal` = `-semanal`\n"
                "`-avg` = `-promedios` · `-avgtop` = `-promedios_tops`"
            ),
            inline=False,
        )

        # ─── Page 4: Gráficos + Tips + Utilidades ────────────────────────
        e4 = discord.Embed(
            title="📈 Gráficos, Tips y Utilidades",
            description="Visualizaciones, consejos y herramientas.\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=COLOR,
        )
        e4.set_thumbnail(url=BOT_THUMBNAIL)

        e4.add_field(
            name="📈 Gráficos Interactivos",
            value=(
                "```\n"
                "-graph <clan>       Gráfico de un clan\n"
                "-graph all          Todos los jugadores\n"
                "```\n"
                "Atajos: `-graficoldh`, `-graficosae`, `-graficofi`, etc."
            ),
            inline=False,
        )

        e4.add_field(
            name="💡 Consejos de Juego",
            value=(
                "```\n"
                "-tips               Tips generales (5 random)\n"
                "-tips <kit>         Tips por kit\n"
                "-tips_para <jugador> Tips personalizados\n"
                "```\n"
                "Kits: `rifleman` · `medic` · `automatic rifleman` · `grenadier`\n"
                "`sniper` · `lat` · `hat` · `combat engineer`"
            ),
            inline=False,
        )

        e4.add_field(
            name="⏳ Utilidades",
            value=(
                "```\n"
                "-timer <DD/MM/YYYY> <HH:MM>\n"
                "  Countdown con soporte multi-timezone\n"
                "  Reaccioná con 🇦🇷🇲🇽🇪🇸🇨🇱🇨🇴 para tu zona\n"
                "\n"
                "-guias    Guías de PR\n"
                "-web      Página principal LDH\n"
                "-vis      Visualizador 2D\n"
                "```"
            ),
            inline=False,
        )

        # ─── Page 5: Administración ──────────────────────────────────────
        e5 = discord.Embed(
            title="🛡️ Administración",
            description="Comandos para admins del servidor.\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=COLOR,
        )
        e5.set_thumbnail(url=BOT_THUMBNAIL)

        e5.add_field(
            name="🎭 Roles Automáticos",
            value=(
                "```\n"
                "-message <emoji> <rol> <texto>\n"
                "  Crear mensaje de rol por reacción\n"
                "\n"
                "-boton_rol <rol> <label> <texto>\n"
                "  Crear mensaje de rol por botón\n"
                "  (persiste tras reinicios)\n"
                "```"
            ),
            inline=False,
        )

        e5.add_field(
            name="📊 Leaderboard Automático",
            value=(
                "```\n"
                "-set_leaderboard_channel <#canal>\n"
                "  Activar top 10 semanal automático\n"
                "\n"
                "-remove_leaderboard_channel\n"
                "  Desactivar leaderboard automático\n"
                "```"
            ),
            inline=False,
        )

        e5.add_field(
            name="⚙️ Sistema",
            value=(
                "`-apagar` · `-shutdown` — Apagar bot (solo owner)\n"
                "`-hola` · `-hi` — Probar que el bot responde"
            ),
            inline=False,
        )

        # ─── Page 6: Estadísticas de Demos ────────────────────────────────
        e6 = discord.Embed(
            title="🎬 Estadísticas de Demos",
            description="Comandos basados en datos de .PRdemo.\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=COLOR,
        )
        e6.set_thumbnail(url=BOT_THUMBNAIL)

        e6.add_field(
            name="📊 Datos Detallados",
            value=(
                "```\n"
                "-kits <jugador>       Kits más usados\n"
                "-vehiculos <jugador>  Stats de vehículos\n"
                "-revives <jugador>    Revives dados/recibidos\n"
                "-armas <jugador>      Armas más letales\n"
                "-mapa <nombre>        Estadísticas de mapas\n"
                "-perfil_demo <jugador> Perfil completo de demos\n"
                "```"
            ),
            inline=False,
        )

        e6.add_field(
            name="🔬 Análisis Avanzado",
            value=(
                "```\n"
                "-rol <jugador>        Efectividad por kit/rol\n"
                "-winrate <jugador>    Análisis de victorias\n"
                "-consistencia <jugador> Varianza y fiabilidad\n"
                "-mapa_perfil <jugador> Rendimiento por mapa\n"
                "-teamwork <jugador>   Contribución al equipo\n"
                "-clan_fortalezas <clan> Análisis SWOT del clan\n"
                "```"
            ),
            inline=False,
        )

        e6.add_field(
            name="🏆 Rankings por Período",
            value=(
                "```\n"
                "-top_periodo <periodo> [N] [metrica]\n"
                "  Periodos: dia, semana, mes, todo\n"
                "  Métricas: kills, kd, score,\n"
                "    revives, teamwork\n"
                "\n"
                "Atajos:\n"
                "-top_semana         Top semanal\n"
                "-top_mes            Top mensual\n"
                "-top_dia            Top del día\n"
                "```"
            ),
            inline=False,
        )

        e6.add_field(
            name="💡 Aliases de análisis",
            value=(
                "`-rol` = `-role` = `-kit_analysis`\n"
                "`-winrate` = `-wr`\n"
                "`-consistencia` = `-consistency` = `-varianza`\n"
                "`-mapa_perfil` = `-map_profile` = `-mapas`\n"
                "`-teamwork` = `-tw`\n"
                "`-clan_fortalezas` = `-clan_foda` = `-clan_analysis`"
            ),
            inline=False,
        )

        e6.add_field(
            name="📡 Modos de Datos",
            value=(
                "El bot puede mostrar datos de distintas fuentes:\n"
                "• **PRStats** — Solo datos de prstats.realitymod.org\n"
                "• **Demos** — Solo datos parseados de .PRdemo\n"
                "• **Combinado** — Ambas fuentes (por defecto)\n\n"
                "Usá los botones debajo para cambiar el modo."
            ),
            inline=False,
        )

        # ─── Build pages ──────────────────────────────────────────────────
        pages = [e1, e2, e3, e4, e5, e6]
        for page in pages:
            page.set_footer(text="También funciona con /slash commands")

        view = PaginationView(pages, author_id=ctx.author.id)
        msg = await ctx.send(embed=pages[0], view=view)
        view.message = msg

        # Send mode selector as a second message
        mode_labels = {"prstats": "PRStats", "demos": "Demos", "combined": "Combinado"}
        current_mode = self.bot.guild_settings.get_mode(ctx.guild.id) if ctx.guild else "combined"
        mode_label = mode_labels.get(current_mode, "Combinado")
        mode_view = ModeSelectorView(self.bot.guild_settings, ctx.guild.id if ctx.guild else 0)
        await ctx.send(
            f"📡 Modo de datos actual: **{mode_label}**",
            view=mode_view,
        )

    # ── Redirect -help to -ayuda (separate command to avoid conflict) ────

    @commands.command(name="help", hidden=True)
    async def help_redirect(self, ctx: commands.Context):
        await self.ayuda(ctx)


async def setup(bot: commands.Bot):
    await bot.add_cog(Misc(bot))
