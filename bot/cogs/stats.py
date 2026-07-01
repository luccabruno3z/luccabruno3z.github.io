"""Stats cog -- estadisticas, top, buscar_usuario, promedios, promedios_tops, tendencia, perfil, ranking_semanal, mejora."""

import json
import logging
import math
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord
from discord.ext import commands
from discord import app_commands

from bot.config import (
    CLAN_EMOJIS,
    BOT_THUMBNAIL,
    METRIC_KEY_MAP,
    all_players_url,
    json_url,
    performance_color,
    BASE_URL,
    clan_logo_url,
)
from bot.services.clan_registry import clan_choices
from bot.services.chart_renderer import render_bar_chart, render_horizontal_bars, render_radar_chart, render_ranking_change_chart
from bot.ui.player_card import PlayerCard
from bot.ui.player_card_actions import build_actions
from bot.ui.player_hub import PlayerHubView
from bot.assets.clan_mapping import get_clan_emoji
from bot.utils import (
    format_number,
    find_player,
    progress_bar,
    percentile,
    rank_medal,
    tier_badge,
    tier_emoji,
    _tier_name,
    classify_playstyle,
    experience_badge,
    sample_reliability,
    sigmoid_penalty_display,
    stat_confidence_warning,
    activity_index_display,
    standard_footer,
    get_player_archetype,
    get_player_archetype_desc,
    get_player_ratings,
    get_player_radar,
    ratings_display,
)
from bot.assets.kit_mapping import get_kit_display
from bot.views.pagination import PaginationView
from bot.views.stats import StatsView
from bot.views.demo_details import DemoDetailsView

logger = logging.getLogger(__name__)


# ── Autocomplete helpers ───────────────────────────────────────────────────

async def player_name_autocomplete(
    interaction: discord.Interaction, current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete for player names, filtering by partial input."""
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


# ── Choices / autocomplete for top command ─────────────────────────────────
# `categoria` es autocomplete (no choices estáticos): hay >25 clanes y Discord
# limita choices a 25; además así se deriva de bot.clans (data-driven).

async def categoria_autocomplete(
    interaction: discord.Interaction, current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete de categorías de -top: 'general' + clanes de bot.clans."""
    return clan_choices(interaction.client, current, extra=["general"])


METRICA_CHOICES = [
    app_commands.Choice(name="performance", value="performance"),
    app_commands.Choice(name="kd", value="kd"),
    app_commands.Choice(name="kills", value="kills"),
    app_commands.Choice(name="deaths", value="deaths"),
    app_commands.Choice(name="rounds", value="rounds"),
]

METRICA_PROMEDIOS_CHOICES = [
    app_commands.Choice(name="performance", value="performance"),
    app_commands.Choice(name="kd", value="kd"),
    app_commands.Choice(name="kills", value="kills"),
    app_commands.Choice(name="deaths", value="deaths"),
    app_commands.Choice(name="rounds", value="rounds"),
    app_commands.Choice(name="score", value="score"),
]


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Helper ────────────────────────────────────────────────────────────

    @property
    def fetcher(self):
        return self.bot.data_fetcher

    # ── -estadisticas <jugador> ───────────────────────────────────────────

    @commands.hybrid_command(aliases=["stats", "st", "e"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    @app_commands.describe(jugador="Nombre del jugador")
    @app_commands.autocomplete(jugador=player_name_autocomplete)
    async def estadisticas(self, ctx: commands.Context, jugador: str = None):
        if not jugador:
            await ctx.send(
                "❗ Por favor, proporciona un nombre de jugador. "
                "Ejemplo: `-estadisticas W4RR10R`."
            )
            return

        await ctx.defer()

        try:
            data = await self.fetcher.fetch_all_players()
        except Exception as e:
            await ctx.send("❌ Error al conectar con la base de datos. Inténtalo más tarde.")
            logger.error("Error fetching all players: %s", e)
            return

        # Sort by Performance Score for global ranking
        jugadores_ordenados = sorted(
            data, key=lambda x: x.get("Performance Score", 0), reverse=True
        )

        jugador_encontrado = find_player(jugadores_ordenados, jugador)

        if not jugador_encontrado:
            await ctx.send(f"⚠️ Jugador '{jugador}' no encontrado. Probá `-buscar <nombre>` para verificar.")
            return

        jugador_lower = jugador_encontrado["Player"].lower()
        ranking_global = next(
            (i + 1 for i, entry in enumerate(jugadores_ordenados) if entry["Player"].lower() == jugador_lower),
            "N/A",
        )

        # Clan ranking
        jugadores_clan = [
            e for e in jugadores_ordenados
            if e.get("Clan") == jugador_encontrado.get("Clan")
        ]
        ranking_clan = next(
            (i + 1 for i, e in enumerate(jugadores_clan) if e["Player"].lower() == jugador_lower),
            "N/A",
        )

        ps = jugador_encontrado.get("Performance Score", 0)

        tier_config = None
        try:
            tier_config = await self.fetcher.fetch_tier_config()
        except Exception:
            pass
        thresholds = tier_config.get("thresholds") if isinstance(tier_config, dict) else None

        color = performance_color(ps, thresholds)

        clan = jugador_encontrado.get("Clan", "N/A")
        clan_image_url = clan_logo_url(clan)

        total_deaths = jugador_encontrado.get("Total Deaths", 0)
        rounds_played = jugador_encontrado.get("Rounds", 1)
        deaths_per_round = total_deaths / rounds_played if rounds_played > 0 else 0

        # Fetch history for trend indicator
        trend = ""
        try:
            safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', jugador)
            history_url = f"{BASE_URL}/graphs/history/{safe_name}_history.json"
            history_data = await self.fetcher.fetch_json(history_url, use_stale_on_error=False)
            if isinstance(history_data, list) and len(history_data) >= 2:
                prev_ps = history_data[-2].get("Performance Score", 0)
                curr_ps = history_data[-1].get("Performance Score", 0)
                if curr_ps > prev_ps:
                    trend = " 📈"
                elif curr_ps < prev_ps:
                    trend = " 📉"
                else:
                    trend = " ➡️"
        except Exception:
            logger.debug("Could not fetch history for trend indicator for %s", jugador)

        # Compute playstyle and tier
        kd = jugador_encontrado["K/D Ratio"]
        kpr = jugador_encontrado.get("Kills per Round", 0)
        spr = jugador_encontrado.get("Score per Round", 0)
        total_kills = jugador_encontrado.get("Total Kills", 0)
        total_score = jugador_encontrado.get("Total Score", 0)

        style_emoji, style_name = get_player_archetype(jugador_encontrado)
        badge = tier_badge(ps, thresholds)
        exp_badge = experience_badge(rounds_played)
        reliability = sample_reliability(rounds_played)

        # Collect all KPR values for percentile
        all_kpr = [p.get("Kills per Round", 0) for p in data]

        arch_desc = get_player_archetype_desc(jugador_encontrado)
        desc_lines = [
            f"{badge} · {style_emoji} {style_name}",
            f"{exp_badge} · {reliability}",
            f"Ranking Global: **#{ranking_global}** · Ranking Clan: **#{ranking_clan}**",
        ]
        if arch_desc:
            desc_lines.insert(1, f"*{arch_desc}*")

        # ── Build the Components V2 player card ────────────────────────────
        tname = _tier_name(ps, thresholds)
        temoji = tier_emoji(ps, thresholds)
        archetype = f"{style_emoji} {style_name}"

        # Breakdown bars: normalized components + rating indices (0-100).
        norm_kd = jugador_encontrado.get("Normalized_KD", 0)
        norm_score = jugador_encontrado.get("Normalized_Score", 0)
        norm_kpr = jugador_encontrado.get("Normalized_Kills_Per_Round", 0)
        norm_rounds = jugador_encontrado.get("Normalized_Rounds", 0)
        breakdown = [
            ("Combate (K/D)", norm_kd * 100),
            ("Puntuación (SPR)", norm_score * 100),
            ("Agresividad (KPR)", norm_kpr * 100),
            ("Experiencia", norm_rounds * 100),
        ]
        ratings = get_player_ratings(jugador_encontrado)
        if ratings:
            breakdown += [
                ("Índice Combate", ratings.get("combat", 0)),
                ("Índice Táctico", ratings.get("tactical", 0)),
                ("Índice Fiabilidad", ratings.get("reliability", 0)),
                ("Índice Impacto", ratings.get("impact", 0)),
            ]

        # Next-tier progress.
        next_tier = None
        if thresholds and ps < thresholds.get("elite", 0.70):
            for _key, _name in (("soldado", "Soldado"), ("experimentado", "Experimentado"),
                                ("veterano", "Veterano"), ("elite", "Elite")):
                _val = thresholds.get(_key, 0)
                if ps < _val:
                    next_tier = (_name, _val - ps)
                    break

        # Cautions (low sample / confidence / penalty).
        warn_lines = []
        if rounds_played < 50:
            warn_lines.append(
                f"Con {rounds_played} rondas tus stats aún no son representativos — "
                f"necesitás {50 - rounds_played} más para aparecer en `-top`."
            )
        else:
            _cw = stat_confidence_warning(rounds_played)
            if _cw:
                warn_lines.append(_cw.strip())
        _penalty = sigmoid_penalty_display(rounds_played)
        if _penalty:
            warn_lines.append(_penalty)
        warning = "\n".join(warn_lines) or None

        # Highlights + actividad (última vez / tiempo jugado) desde la data de demos.
        highlights = None
        activity_line = None
        try:
            demo_data = await self.fetcher.fetch_player_details()
            demo_player = find_player(demo_data, jugador_encontrado["Player"], key="ign") if demo_data else None
            if demo_player:
                _hl = []
                _best = demo_player.get("best_round")
                _worst = demo_player.get("worst_round")
                if isinstance(_best, dict) and _best.get("kills", 0) > 0:
                    _hl.append(f"🏆 Mejor: {_best.get('kills', 0)} kills en {_best.get('map', '?')}")
                if isinstance(_worst, dict):
                    _hl.append(f"💀 Peor: {_worst.get('kills', 0)} kills en {_worst.get('map', '?')}")
                if _hl:
                    highlights = "🎯 **Rondas destacadas**\n" + "\n".join(_hl)
                # Última vez visto (último demo capturado) + tiempo jugado (registrado).
                _last = demo_player.get("last_round_date")
                _played = demo_player.get("played_seconds", 0) or 0
                _parts = []
                if _last:
                    _parts.append(f"📅 Última vez: **{_last}**")
                if _played >= 60:
                    _hours = _played / 3600
                    _t = f"{_hours:.1f} h" if _hours >= 1 else f"{int(_played // 60)} min"
                    _parts.append(f"⏱️ Tiempo jugado: **{_t}** *(registrado)*")
                if _parts:
                    activity_line = " · ".join(_parts)
        except Exception:
            pass  # demo data optional

        footer = standard_footer(jugador_encontrado)
        _ai = jugador_encontrado.get("Activity Index")
        _ai_text = activity_index_display(_ai) if _ai is not None else ""
        if _ai_text:
            footer = f"{footer} · {_ai_text}"

        # Action buttons — demo-based actions only in demos/combined modes.
        mode = self.bot.guild_settings.get_mode(ctx.guild.id) if ctx.guild else "combined"
        actions = build_actions(jugador_encontrado["Player"])
        if mode not in ("combined", "demos"):
            actions = [a for a in actions if a.action in ("hist", "cmp", "glos")]

        card = PlayerCard(
            jugador_encontrado,
            tier_name=tname,
            tier_emoji=temoji,
            archetype=archetype,
            ranking_global=ranking_global,
            ranking_clan=ranking_clan,
            clan_logo_url=clan_image_url,
            breakdown=breakdown,
            footer=footer,
            trend=trend,
            next_tier=next_tier,
            warning=warning,
            highlights=highlights,
            activity=activity_line,
            accent=color.value,
            actions=actions,
        )
        await ctx.send(view=card)

    # ── -top <cantidad> <categoria> <metrica> ─────────────────────────────

    @commands.hybrid_command(aliases=["ranking", "leaderboard", "lb"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    @app_commands.describe(
        cantidad="Cantidad de jugadores a mostrar",
        categoria="Categoría (clan o general)",
        metrica="Métrica para ordenar",
        activos="Filtrar solo jugadores activos",
    )
    @app_commands.choices(metrica=METRICA_CHOICES)
    @app_commands.autocomplete(categoria=categoria_autocomplete)
    async def top(
        self,
        ctx: commands.Context,
        cantidad: int = 15,
        categoria: str = "general",
        metrica: str = "performance",
        activos: bool = False,
    ):
        # Check data mode
        mode = self.bot.guild_settings.get_mode(ctx.guild.id) if ctx.guild else "combined"

        categorias = self.bot.clans.top_categories()
        if categoria.lower() not in categorias:
            await ctx.send(
                "❗ **Categoría inválida.** Usá `general` o un clan válido "
                "(autocompletado en el slash command)."
            )
            return

        if cantidad <= 0:
            await ctx.send("❗ **La cantidad debe ser mayor a 0.**")
            return

        # Clamp to max 50
        cantidad = min(cantidad, 50)

        metricas_validas = ["performance", "kd", "kills", "deaths", "rounds"]
        if metrica not in metricas_validas:
            await ctx.send(
                "❗ **Métrica inválida.** Las métricas válidas son:\n"
                "`performance`, `kd`, `kills`, `deaths`, `rounds`."
            )
            return

        await ctx.defer()

        # If mode is "demos", fetch from demo player_details instead
        if mode == "demos":
            try:
                demo_data = await self.fetcher.fetch_player_details()
            except Exception as e:
                await ctx.send("❌ **Error al conectar con los datos de demos.** Inténtalo más tarde.")
                logger.error("Error: %s", e)
                return

            # Map demo data keys to prstats-compatible keys
            demo_metric_map = {
                "performance": "total_score",
                "kd": None,  # computed
                "kills": "total_kills",
                "deaths": "total_deaths",
                "rounds": "rounds_played",
            }

            def demo_sort_key(p):
                if metrica == "kd":
                    deaths = p.get("total_deaths", 1) or 1
                    return p.get("total_kills", 0) / deaths
                return p.get(demo_metric_map.get(metrica, "total_score"), 0)

            demo_sorted = sorted(demo_data, key=demo_sort_key, reverse=True)[:cantidad]

            lines: list[str] = []
            for index, p in enumerate(demo_sorted, start=1):
                nombre = p.get("ign", "Desconocido")
                medal = rank_medal(index)
                if metrica == "kd":
                    deaths = p.get("total_deaths", 1) or 1
                    valor = p.get("total_kills", 0) / deaths
                    lines.append(f"{medal} **{nombre}** — {valor:.2f}")
                else:
                    valor = p.get(demo_metric_map.get(metrica, "total_score"), 0)
                    lines.append(f"{medal} **{nombre}** — {format_number(valor)}")

            embed = discord.Embed(
                title=f"🏆 **Top {cantidad} Jugadores** ({categoria.upper()} - {metrica}) [Demos]",
                description=f"Clasificación basada en **{metrica}** (datos de demos).",
                color=discord.Color.orange(),
            )
            embed.set_thumbnail(url=BOT_THUMBNAIL)
            embed.add_field(
                name="🔝 **Ranking**",
                value="\n".join(lines) if lines else "No hay jugadores en esta categoría.",
                inline=False,
            )
            embed.set_footer(text="Datos de demos (.PRdemo)")

            # Build chart
            chart_names = [p.get("ign", "?") for p in demo_sorted][:15]
            if metrica == "kd":
                chart_values = [p.get("total_kills", 0) / (p.get("total_deaths", 1) or 1) for p in demo_sorted][:15]
            else:
                chart_values = [p.get(demo_metric_map.get(metrica, "total_score"), 0) for p in demo_sorted][:15]
            buf = render_bar_chart(chart_names, chart_values, f"Top {metrica}", "Jugadores", metrica)
            file = discord.File(buf, filename="top_chart.png")
            embed.set_image(url="attachment://top_chart.png")

            await ctx.send(embed=embed, file=file)
            return

        clan_name = categorias[categoria.lower()]
        try:
            if clan_name is None:
                data = await self.fetcher.fetch_all_players()
            else:
                data = await self.fetcher.fetch_clan_players(clan_name)
        except Exception as e:
            await ctx.send("❌ **Error al conectar con la base de datos.** Inténtalo más tarde.")
            logger.error("Error: %s", e)
            return

        metric_key = METRIC_KEY_MAP.get(metrica, metrica)

        # Filter out players with < 50 rounds (unreliable sample)
        MIN_ROUNDS_FOR_RANKING = 50
        reliable_data = [p for p in data if p.get("Rounds", 0) >= MIN_ROUNDS_FOR_RANKING]
        excluded_count = len(data) - len(reliable_data)

        if activos:
            reliable_data = [p for p in reliable_data if p.get("Activity Index", 0) >= 40]

        jugadores_ordenados = sorted(
            reliable_data, key=lambda x: x.get(metric_key, 0), reverse=True
        )

        cantidad = min(cantidad, len(jugadores_ordenados))
        top_jugadores = jugadores_ordenados[:cantidad]

        # Build lines for all players
        max_value = top_jugadores[0].get(metric_key, 0) if top_jugadores else 1
        lines: list[str] = []
        for index, jugador_entry in enumerate(top_jugadores, start=1):
            nombre = jugador_entry.get("Player", "Desconocido")
            valor_metrica = jugador_entry.get(metric_key, 0)
            clan = jugador_entry.get("Clan", "N/A")
            clan_emoji = get_clan_emoji(clan)
            medal = rank_medal(index)
            tier = " " + tier_emoji(valor_metrica) if metrica == "performance" else ""
            lines.append(f"{medal} **{nombre}** [{clan}] — {format_number(valor_metrica)}{tier}")

        # Footer info
        excluded_note = f" · {excluded_count} jugadores excluidos (<50 rondas)" if excluded_count else ""
        demo_note = " · Datos de demos también disponibles (-ayuda)" if mode == "combined" else ""
        footer_text = standard_footer(data) + excluded_note + demo_note

        ranking_desc = (
            f"Clasificación basada en **{metrica}**. "
            f"Mínimo 50 rondas para participar."
        )

        # Build chart from top players
        chart_names = [p.get("Player", "?") for p in top_jugadores][:15]
        chart_values = [p.get(metric_key, 0) for p in top_jugadores][:15]
        buf = render_bar_chart(chart_names, chart_values, f"Top {metrica}", "Jugadores", metrica)
        chart_file = discord.File(buf, filename="top_chart.png")

        per_page = 8
        if len(lines) > per_page:
            # Send chart as a separate message so it doesn't disappear on page change
            await ctx.send(file=chart_file)

            pages: list[discord.Embed] = []
            for i in range(0, len(lines), per_page):
                chunk = lines[i : i + per_page]
                page_num = (i // per_page) + 1
                total_pages = (len(lines) + per_page - 1) // per_page
                embed = discord.Embed(
                    title=f"🏆 **Top {cantidad} Jugadores** ({categoria.upper()} - {metrica})",
                    description=f"{ranking_desc}\nPágina {page_num}/{total_pages}",
                    color=discord.Color.orange(),
                )
                embed.set_thumbnail(url=BOT_THUMBNAIL)
                embed.add_field(
                    name="🔝 **Ranking**",
                    value="\n".join(chunk),
                    inline=False,
                )
                embed.set_footer(text=footer_text)
                pages.append(embed)
            view = PaginationView(pages)
            msg = await ctx.send(embed=pages[0], view=view)
            view.message = msg
        else:
            embed = discord.Embed(
                title=f"🏆 **Top {cantidad} Jugadores** ({categoria.upper()} - {metrica})",
                description=ranking_desc,
                color=discord.Color.orange(),
            )
            embed.set_thumbnail(url=BOT_THUMBNAIL)
            embed.add_field(
                name="🔝 **Ranking**",
                value="\n".join(lines) if lines else "No hay jugadores con suficientes rondas en esta categoría.",
                inline=False,
            )
            embed.set_footer(text=footer_text)
            embed.set_image(url="attachment://top_chart.png")
            await ctx.send(embed=embed, file=chart_file)

    # ── -buscar_usuario <parte_nombre> ────────────────────────────────────

    @commands.hybrid_command(aliases=["buscar", "search", "find"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    @app_commands.describe(nombre_parcial="Parte del nombre de usuario a buscar")
    async def buscar_usuario(self, ctx: commands.Context, *, nombre_parcial: str = None):
        if not nombre_parcial:
            await ctx.send(
                "❗ Por favor, proporciona una parte del nombre de usuario que deseas buscar. "
                "Ejemplo: `-buscar_usuario parte_del_nombre`."
            )
            return

        try:
            data = await self.fetcher.fetch_all_players()
        except Exception as e:
            await ctx.send("❌ Error al conectar con la base de datos. Inténtalo más tarde.")
            logger.error("Error: %s", e)
            return

        resultados = [
            j for j in data if nombre_parcial.lower() in j["Player"].lower()
        ]

        if not resultados:
            await ctx.send(
                f"⚠️ No se encontraron usuarios que contengan '{nombre_parcial}' en su nombre."
            )
            return

        # Sort results by Performance Score (best first)
        resultados.sort(key=lambda x: x.get("Performance Score", 0), reverse=True)

        def _build_search_embed(players: list, page_num: int = 0, total_pages: int = 1) -> discord.Embed:
            embed = discord.Embed(
                title="🔍 Resultados de Búsqueda",
                description=(
                    f"**{len(resultados)}** jugadores encontrados con `{nombre_parcial}`"
                ),
                color=discord.Color.green(),
            )
            embed.set_thumbnail(url=BOT_THUMBNAIL)
            for jugador_entry in players:
                clan = jugador_entry.get("Clan", "N/A")
                clan_emoji = get_clan_emoji(clan)
                ps_val = jugador_entry.get("Performance Score", 0)
                embed.add_field(
                    name=f"{clan_emoji} {jugador_entry['Player']}",
                    value=(
                        f"🏷️ **Clan**: {clan}\n"
                        f"💥 **K/D**: {jugador_entry['K/D Ratio']:.2f}\n"
                        f"🌟 **Performance**: {ps_val:.2f} {tier_emoji(ps_val)}"
                    ),
                    inline=True,
                )
            embed.set_footer(text=standard_footer(data))
            return embed

        per_page = 10
        if len(resultados) > per_page:
            pages: list[discord.Embed] = []
            total_pages = math.ceil(len(resultados) / per_page)
            for i in range(0, len(resultados), per_page):
                chunk = resultados[i : i + per_page]
                pages.append(_build_search_embed(chunk, i // per_page, total_pages))
            view = PaginationView(pages)
            msg = await ctx.send(embed=pages[0], view=view)
            view.message = msg
        else:
            await ctx.send(embed=_build_search_embed(resultados))

    # ── -promedios ────────────────────────────────────────────────────────

    @commands.hybrid_command(aliases=["avg", "averages"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def promedios(self, ctx: commands.Context):
        try:
            data = await self.fetcher.fetch_clan_averages()
        except Exception as e:
            await ctx.send("Error al conectar con la base de datos. Inténtalo más tarde.")
            logger.error("Error: %s", e)
            return

        if not isinstance(data, list):
            await ctx.send("El formato de los datos no es válido.")
            return

        embed = discord.Embed(
            title="🏆 Promedios de Clanes",
            description="Ranking de clanes ordenado por **Performance Score**.",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=BOT_THUMBNAIL)

        clan_names = []
        performance_scores = []

        # Sort clans by Performance Score (best first)
        sorted_data = sorted(data, key=lambda c: c.get("Performance Score", 0), reverse=True)
        max_ps = sorted_data[0].get("Performance Score", 1) if sorted_data else 1

        for rank_idx, clan_data in enumerate(sorted_data, start=1):
            clan_name = clan_data.get("Clan", "Desconocido")
            kd_ratio = clan_data.get("K/D Ratio", 0)
            score_per_round = clan_data.get("Score per Round", 0)
            kills_per_round = clan_data.get("Kills per Round", 0)
            ps = clan_data.get("Performance Score", 0)

            clan_names.append(clan_name)
            performance_scores.append(ps)

            clan_emoji = get_clan_emoji(clan_name)
            medal = rank_medal(rank_idx)
            bar = progress_bar(ps, max_ps, 8)

            embed.add_field(
                name=f"{medal} {clan_name} {clan_emoji}",
                value=(
                    f"💥 K/D: `{kd_ratio:.2f}` · 🎯 Score/R: `{score_per_round:.2f}`\n"
                    f"🔫 Kills/R: `{kills_per_round:.2f}` · 🌟 Perf: `{bar}` **{ps:.2f}**"
                ),
                inline=False,
            )

        buf = render_bar_chart(
            clan_names,
            performance_scores,
            "Performance Score de Clanes",
            "Clanes",
            "Performance Score",
        )
        file = discord.File(buf, filename="performance_scores_clanes.png")
        embed.set_image(url="attachment://performance_scores_clanes.png")
        embed.set_footer(text=standard_footer(data))
        await ctx.send(embed=embed, file=file)

    # ── -promedios_tops <cantidad> <metrica> ──────────────────────────────

    @commands.hybrid_command(aliases=["avgtop", "topavg"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    @app_commands.describe(
        cantidad="Cantidad de mejores jugadores por clan",
        metrica="Métrica para calcular promedios",
    )
    @app_commands.choices(metrica=METRICA_PROMEDIOS_CHOICES)
    async def promedios_tops(
        self,
        ctx: commands.Context,
        cantidad: int = 15,
        metrica: str = "performance",
    ):
        if cantidad <= 0:
            await ctx.send("❗ **La cantidad debe ser mayor a 0.**")
            return

        metricas_validas = ["performance", "kd", "kills", "deaths", "rounds", "score"]
        if metrica not in metricas_validas:
            await ctx.send(
                "❗ **Métrica inválida.** Las métricas válidas son:\n"
                "`performance`, `kd`, `kills`, `deaths`, `rounds`, `score`."
            )
            return

        await ctx.defer()

        try:
            data = await self.fetcher.fetch_all_players()
        except Exception as e:
            await ctx.send("❌ **Error al conectar con la base de datos.** Inténtalo más tarde.")
            logger.error("Error: %s", e)
            return

        metric_key = METRIC_KEY_MAP.get(metrica, metrica)

        # Group players by clan
        clans: dict[str, list] = {}
        for player in data:
            cn = player.get("Clan", "Sin Clan")
            clans.setdefault(cn, []).append(player)

        embed = discord.Embed(
            title=f"🏆 Promedios Top {cantidad} por Clan ({metrica.capitalize()})",
            description=f"Promedio de **{metrica}** usando los mejores **{cantidad}** jugadores de cada clan.",
            color=discord.Color.green(),
        )
        embed.set_thumbnail(url=BOT_THUMBNAIL)

        clan_names = []
        avg_values = []

        clan_averages = []
        for cn, players in clans.items():
            top_players = sorted(
                players, key=lambda x: x.get(metric_key, 0), reverse=True
            )[:cantidad]
            avg = (
                sum(p.get(metric_key, 0) for p in top_players) / len(top_players)
                if top_players
                else 0
            )
            clan_averages.append((cn, avg, len(players)))

        # Sort clans by average value (best first)
        clan_averages.sort(key=lambda x: x[1], reverse=True)
        max_avg = clan_averages[0][1] if clan_averages else 1

        for rank_idx, (cn, avg, total) in enumerate(clan_averages, start=1):
            clan_names.append(cn)
            avg_values.append(avg)
            clan_emoji = get_clan_emoji(cn)
            medal = rank_medal(rank_idx)
            bar = progress_bar(avg, max_avg, 8)
            embed.add_field(
                name=f"{medal} {cn} {clan_emoji}",
                value=(
                    f"`{bar}` **{avg:.2f}**\n"
                    f"*{total} jugadores en el clan*"
                ),
                inline=False,
            )

        buf = render_bar_chart(
            clan_names,
            avg_values,
            f"Promedio {metrica.capitalize()} de los Mejores {cantidad} Jugadores por Clan",
            "Clanes",
            f"Promedio {metrica.capitalize()}",
        )
        file = discord.File(buf, filename="promedios_tops.png")
        embed.set_image(url="attachment://promedios_tops.png")
        embed.set_footer(text=standard_footer(data))
        await ctx.send(embed=embed, file=file)


    # ── -tendencia <jugador> ──────────────────────────────────────────────

    @commands.hybrid_command(aliases=["trend", "evolucion"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    @app_commands.describe(jugador="Nombre del jugador")
    @app_commands.autocomplete(jugador=player_name_autocomplete)
    async def tendencia(self, ctx: commands.Context, jugador: str = None):
        """Muestra la tendencia de rendimiento de un jugador."""
        if not jugador:
            await ctx.send(
                "❗ Por favor, proporciona un nombre de jugador. "
                "Ejemplo: `-tendencia W4RR10R`."
            )
            return

        await ctx.defer()

        # Also fetch current player data for context
        try:
            all_data = await self.fetcher.fetch_all_players()
        except Exception:
            all_data = []

        player_data = find_player(all_data, jugador) if all_data else None
        actual_name = player_data["Player"] if player_data else jugador

        safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', actual_name)
        history_url = f"{BASE_URL}/graphs/history/{safe_name}_history.json"

        try:
            history_data = await self.fetcher.fetch_json(history_url, use_stale_on_error=False)
        except Exception:
            await ctx.send(f"No se encontró historial para **{actual_name}**. Los datos de historial se generan cada hora.")
            return

        if not isinstance(history_data, list) or len(history_data) < 2:
            await ctx.send(f"**{actual_name}** tiene solo {len(history_data) if isinstance(history_data, list) else 0} capturas. Se necesitan al menos 2 para analizar tendencias.")
            return

        # ── Analyze all entries ──────────────────────────────────────────
        all_scores = [e.get("Performance Score", 0) for e in history_data]
        all_dates = [e.get("Date", "?") for e in history_data]
        current_score = all_scores[-1]
        total_entries = len(all_scores)

        # Short-term (last 5) vs long-term (all)
        short = all_scores[-5:] if len(all_scores) >= 5 else all_scores
        short_changes = [short[i] - short[i-1] for i in range(1, len(short))]
        all_changes = [all_scores[i] - all_scores[i-1] for i in range(1, len(all_scores))]

        short_avg = sum(short_changes) / len(short_changes) if short_changes else 0
        long_avg = sum(all_changes) / len(all_changes) if all_changes else 0

        # Best and worst scores
        best_score = max(all_scores)
        worst_score = min(all_scores)
        best_idx = all_scores.index(best_score)
        worst_idx = all_scores.index(worst_score)

        # Overall change
        total_change = current_score - all_scores[0]

        # Determine trend (short-term weighted more)
        weighted_trend = short_avg * 0.7 + long_avg * 0.3

        if weighted_trend > 0.005:
            trend_arrow = "📈"
            trend_text = "Mejorando"
            trend_color = discord.Color.green()
            trend_desc = "Tu rendimiento viene en alza. ¡Seguí así!"
        elif weighted_trend < -0.005:
            trend_arrow = "📉"
            trend_text = "Declinando"
            trend_color = discord.Color.red()
            trend_desc = "Tu rendimiento bajó últimamente. Revisá tu gameplay con `-mejora`."
        else:
            trend_arrow = "➡️"
            trend_text = "Estable"
            trend_color = discord.Color.gold()
            trend_desc = "Tu rendimiento es consistente. Para subir, probá `-mejora`."

        # Streak detection
        streak = 0
        streak_dir = None
        for i in range(len(all_scores) - 1, 0, -1):
            diff = all_scores[i] - all_scores[i-1]
            if diff > 0.001:
                if streak_dir is None:
                    streak_dir = "up"
                if streak_dir == "up":
                    streak += 1
                else:
                    break
            elif diff < -0.001:
                if streak_dir is None:
                    streak_dir = "down"
                if streak_dir == "down":
                    streak += 1
                else:
                    break
            else:
                break

        streak_text = ""
        if streak >= 3 and streak_dir == "up":
            streak_text = f"🔥 **Racha positiva:** {streak} capturas mejorando consecutivas"
        elif streak >= 3 and streak_dir == "down":
            streak_text = f"❄️ **Racha negativa:** {streak} capturas bajando consecutivas"

        # ── Build embed ──────────────────────────────────────────────────
        embed = discord.Embed(
            title=f"{trend_arrow} Tendencia de {actual_name}",
            description=f"{trend_desc}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            color=trend_color,
        )
        if player_data:
            clan = player_data.get("Clan", "")
            embed.set_thumbnail(url=clan_logo_url(clan))

        # Current status
        bar = progress_bar(current_score, 2.0, 10)
        embed.add_field(
            name="📊 Score Actual",
            value=f"`{bar}` **{current_score:.4f}**\n{tier_badge(current_score)}",
            inline=True,
        )

        # Change summary
        change_sign = "+" if total_change >= 0 else ""
        embed.add_field(
            name="📐 Cambio Total",
            value=(
                f"**{change_sign}{total_change:.4f}**\n"
                f"*En {total_entries} capturas*"
            ),
            inline=True,
        )

        embed.add_field(
            name=f"{trend_arrow} Veredicto",
            value=f"**{trend_text}**",
            inline=True,
        )

        # Short vs long term
        short_sign = "+" if short_avg >= 0 else ""
        long_sign = "+" if long_avg >= 0 else ""
        embed.add_field(
            name="🔎 Análisis Detallado",
            value=(
                f"**Corto plazo** (últ. {len(short)} capturas): `{short_sign}{short_avg:.4f}` por captura\n"
                f"**Largo plazo** ({total_entries} capturas): `{long_sign}{long_avg:.4f}` por captura\n"
                f"\n"
                f"🏆 **Mejor score:** {best_score:.4f} *(captura #{best_idx + 1})*\n"
                f"📉 **Peor score:** {worst_score:.4f} *(captura #{worst_idx + 1})*"
            ),
            inline=False,
        )

        if streak_text:
            embed.add_field(name="🎯 Racha", value=streak_text, inline=False)

        # Tip based on trend
        if weighted_trend < -0.005:
            embed.add_field(
                name="💡 Consejo",
                value="Enfocate en reducir muertes innecesarias. Usá `-perfil` para ver tus puntos débiles y `-mejora` para un plan concreto.",
                inline=False,
            )
        elif weighted_trend > 0.005:
            embed.add_field(
                name="💡 Consejo",
                value="Vas por buen camino. Usá `-perfil` para ver en qué más podés mejorar.",
                inline=False,
            )

        first_date = all_dates[0] if all_dates else "?"
        last_date = all_dates[-1] if all_dates else "?"
        embed.set_footer(text=standard_footer(player_data) + f" · {total_entries} capturas desde {first_date}")
        await ctx.send(embed=embed)

    # ── -perfil <jugador> ────────────────────────────────────────────────

    @commands.hybrid_command(name="perfil", aliases=["profile", "p"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    @app_commands.describe(jugador="Nombre del jugador")
    @app_commands.autocomplete(jugador=player_name_autocomplete)
    async def perfil_cmd(self, ctx: commands.Context, jugador: str = None):
        """Muestra el perfil radar de un jugador comparado con el promedio del clan."""
        if not jugador:
            await ctx.send(
                "❗ Por favor, proporciona un nombre de jugador. "
                "Ejemplo: `-perfil W4RR10R`."
            )
            return

        await ctx.defer()

        try:
            data = await self.fetcher.fetch_all_players()
        except Exception as e:
            await ctx.send("❌ Error al conectar con la base de datos. Inténtalo más tarde.")
            logger.error("Error fetching all players: %s", e)
            return

        # Sort by Performance Score for ranking
        jugadores_ordenados = sorted(
            data, key=lambda x: x.get("Performance Score", 0), reverse=True
        )

        jugador_encontrado = find_player(jugadores_ordenados, jugador)

        if not jugador_encontrado:
            await ctx.send(f"⚠️ Jugador '{jugador}' no encontrado. Probá `-buscar <nombre>` para verificar.")
            return

        jugador_lower = jugador_encontrado["Player"].lower()
        ranking_global = next(
            (i + 1 for i, entry in enumerate(jugadores_ordenados) if entry["Player"].lower() == jugador_lower),
            None,
        )

        clan = jugador_encontrado.get("Clan", "N/A")
        rounds_played = jugador_encontrado.get("Rounds", 1)
        total_deaths = jugador_encontrado.get("Total Deaths", 0)
        deaths_per_round = total_deaths / rounds_played if rounds_played > 0 else 0
        kd = jugador_encontrado.get("K/D Ratio", 0)
        kills_per_round = jugador_encontrado.get("Kills per Round", 0)
        score_per_round = jugador_encontrado.get("Score per Round", 0)

        ps = jugador_encontrado.get("Performance Score", 0)

        # Read pre-computed radar from JSON
        player_radar = get_player_radar(jugador_encontrado)

        if player_radar:
            player_values = {
                "Letalidad": player_radar.get("letalidad", 0),
                "Supervivencia": player_radar.get("supervivencia", 0),
                "Teamwork": player_radar.get("teamwork", 0),
                "Impacto": player_radar.get("impacto", 0),
                "Consistencia": player_radar.get("consistencia", 0),
                "Versatilidad": player_radar.get("versatilidad", 0),
            }
        else:
            # Fallback: compute basic radar from raw stats
            reliable = [p for p in data if p.get("Rounds", 0) >= 10]
            if not reliable:
                reliable = data
            def p95(values):
                if not values:
                    return 1
                s = sorted(values)
                idx = int(len(s) * 0.95)
                return s[min(idx, len(s) - 1)] or 1
            ref_kd = p95([p.get("K/D Ratio", 0) for p in reliable])
            ref_kpr = p95([p.get("Kills per Round", 0) for p in reliable])
            player_values = {
                "Letalidad": min(kills_per_round / ref_kpr, 1.0),
                "Supervivencia": max(0.0, 1.0 - (deaths_per_round / 6.0)),
                "Teamwork": 0.3,
                "Impacto": min(ps / 0.7, 1.0) * 0.5,
                "Consistencia": 0.3,
                "Versatilidad": 0.3,
            }

        # Clan average from pre-computed radars
        clan_players = [p for p in data if p.get("Clan") == clan]
        clan_players_with_radar = [p for p in clan_players if p.get("radar")]
        if clan_players_with_radar:
            radar_keys = ["letalidad", "supervivencia", "teamwork", "impacto", "consistencia", "versatilidad"]
            label_map = {"letalidad": "Letalidad", "supervivencia": "Supervivencia", "teamwork": "Teamwork",
                         "impacto": "Impacto", "consistencia": "Consistencia", "versatilidad": "Versatilidad"}
            clan_avg_values = {}
            for rk in radar_keys:
                avg = sum(p["radar"].get(rk, 0) for p in clan_players_with_radar) / len(clan_players_with_radar)
                clan_avg_values[label_map[rk]] = avg
        else:
            clan_avg_values = {k: 0 for k in player_values}

        # Render radar chart
        buf = render_radar_chart(player_values, clan_avg_values, jugador, clan)

        # Classify playstyle
        playstyle_emoji, playstyle_name = get_player_archetype(jugador_encontrado)

        # Performance tier
        tier_config = None
        try:
            tier_config = await self.fetcher.fetch_tier_config()
        except Exception:
            pass
        thresholds = tier_config.get("thresholds") if isinstance(tier_config, dict) else None

        badge = tier_badge(ps, thresholds)
        color = performance_color(ps, thresholds)

        # Strengths and weaknesses
        stat_labels = {
            "Letalidad": "Letalidad",
            "Supervivencia": "Supervivencia",
            "Teamwork": "Teamwork",
            "Impacto": "Impacto",
            "Consistencia": "Consistencia",
            "Versatilidad": "Versatilidad",
        }
        fortalezas = []
        debilidades = []
        for key in player_values:
            pv = player_values[key]
            cv = clan_avg_values[key]
            if cv > 0:
                ratio = pv / cv
                pct = abs(ratio - 1.0) * 100
                if ratio > 1.1:
                    fortalezas.append(f"✅ {stat_labels[key]} {pct:.0f}% por encima del promedio del clan")
                elif ratio < 0.9:
                    debilidades.append(f"❌ {stat_labels[key]} {pct:.0f}% por debajo del promedio del clan")

        # Build embed
        exp_badge = experience_badge(rounds_played)
        reliability = sample_reliability(rounds_played)

        clan_emoji = get_clan_emoji(clan)
        embed = discord.Embed(
            title=f"📋 Perfil de {jugador}",
            description=(
                f"{badge} · {playstyle_emoji} {playstyle_name}\n"
                f"{exp_badge} · {reliability}\n"
                f"{clan_emoji} **{clan}** · Ranking Global: **#{ranking_global}**"
            ),
            color=color,
        )
        embed.set_thumbnail(url=clan_logo_url(clan))

        if fortalezas:
            embed.add_field(
                name="💪 Fortalezas",
                value="\n".join(fortalezas),
                inline=False,
            )

        if debilidades:
            embed.add_field(
                name="⚠️ Áreas de Mejora",
                value="\n".join(debilidades),
                inline=False,
            )

        if not fortalezas and not debilidades:
            embed.add_field(
                name="📊 Análisis",
                value="El jugador está dentro del promedio del clan en todas las categorías.",
                inline=False,
            )

        ratings = get_player_ratings(jugador_encontrado)
        if ratings:
            embed.add_field(
                name="📊 Índices",
                value=ratings_display(ratings),
                inline=True,
            )

        confidence_warn = stat_confidence_warning(rounds_played)
        if confidence_warn:
            embed.add_field(
                name="\u200b",
                value=confidence_warn.strip(),
                inline=False,
            )

        file = discord.File(buf, filename="radar_perfil.png")
        embed.set_image(url="attachment://radar_perfil.png")

        embed.set_footer(text=standard_footer(jugador_encontrado))

        # Hub unificado: dropdown de tabs (perfil/estadísticas/historial/demos…) +
        # botones de acción (comparar/rondas/📖 glosario). Las tabs de demos solo si el modo lo permite.
        mode = self.bot.guild_settings.get_mode(ctx.guild.id) if ctx.guild else "combined"
        allow_demos = mode in ("combined", "demos")
        view = PlayerHubView(jugador_encontrado["Player"], "perfil", allow_demos)
        await ctx.send(embed=embed, file=file, view=view)

    # ── -ranking_semanal ────────────────────────────────────────────────

    @commands.hybrid_command(aliases=["weekly", "semanal"])
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def ranking_semanal(self, ctx: commands.Context):
        """Muestra los jugadores que más mejoraron y más cayeron en la última semana."""
        await ctx.defer()

        try:
            data = await self.fetcher.fetch_all_players()
        except Exception as e:
            await ctx.send("❌ Error al conectar con la base de datos. Inténtalo más tarde.")
            logger.error("Error: %s", e)
            return

        # Sort by performance and take top 50
        sorted_players = sorted(
            data, key=lambda x: x.get("Performance Score", 0), reverse=True
        )[:50]

        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        weekly_changes = []

        for player in sorted_players:
            name = player.get("Player", "")
            current_ps = player.get("Performance Score", 0)
            safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
            history_url_str = f"{BASE_URL}/graphs/history/{safe_name}_history.json"

            try:
                history_data = await self.fetcher.fetch_json(
                    history_url_str, use_stale_on_error=False
                )
            except Exception:
                continue

            if not isinstance(history_data, list) or len(history_data) < 2:
                continue

            # Find the last entry before 7 days ago
            old_score = None
            for entry in history_data:
                try:
                    entry_date = datetime.strptime(entry["Date"], "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    )
                except (KeyError, ValueError):
                    continue
                if entry_date <= seven_days_ago:
                    old_score = entry.get("Performance Score", 0)

            if old_score is not None:
                change = current_ps - old_score
                weekly_changes.append((name, current_ps, old_score, change))

        if not weekly_changes:
            await ctx.send("No hay suficientes datos históricos para generar el ranking semanal.")
            return

        # Sort by change, filtering to only positive/negative respectively
        risers = sorted(
            [w for w in weekly_changes if w[3] > 0], key=lambda x: x[3], reverse=True
        )[:10]
        fallers = sorted(
            [w for w in weekly_changes if w[3] < 0], key=lambda x: x[3]
        )[:10]

        embed = discord.Embed(
            title="📊 Ranking Semanal",
            description=(
                "Jugadores que más mejoraron y más cayeron en la última semana.\n"
                f"*Basado en los top 50 jugadores · {len(weekly_changes)} con historial disponible*"
            ),
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=BOT_THUMBNAIL)

        # Build a lookup for rounds by player name
        rounds_lookup = {p.get("Player", ""): p.get("Rounds", 0) for p in data}

        # Find max change for progress bar scaling
        max_rise = risers[0][3] if risers else 1
        max_fall = abs(fallers[0][3]) if fallers else 1

        risers_text = ""
        for i, (name, curr, old, change) in enumerate(risers, 1):
            low_sample = " ⚠️" if rounds_lookup.get(name, 0) < 50 else ""
            medal = rank_medal(i)
            bar = progress_bar(change, max_rise, 6)
            risers_text += f"{medal} **{name}** `{bar}`\n╰ {old:.2f} → **{curr:.2f}** (+{change:.2f}){low_sample}\n"

        fallers_text = ""
        for i, (name, curr, old, change) in enumerate(fallers, 1):
            low_sample = " ⚠️" if rounds_lookup.get(name, 0) < 50 else ""
            medal = rank_medal(i)
            bar = progress_bar(abs(change), max_fall, 6)
            fallers_text += f"{medal} **{name}** `{bar}`\n╰ {old:.2f} → **{curr:.2f}** ({change:.2f}){low_sample}\n"

        embed.add_field(
            name="📈 Top 10 Mejoras",
            value=risers_text if risers_text else "Sin datos suficientes.",
            inline=False,
        )
        embed.add_field(
            name="📉 Top 10 Caídas",
            value=fallers_text if fallers_text else "Sin datos suficientes.",
            inline=False,
        )
        embed.set_footer(text=standard_footer(data))

        # Build ranking change chart from risers
        if risers:
            chart_names = [r[0] for r in risers]
            chart_changes = [r[3] for r in risers]
            buf = render_ranking_change_chart(chart_names, chart_changes, "Top Mejoras Semanales")
            file = discord.File(buf, filename="ranking_semanal.png")
            embed.set_image(url="attachment://ranking_semanal.png")
            await ctx.send(embed=embed, file=file)
        else:
            await ctx.send(embed=embed)

    # ── -mejora <jugador> ──────────────────────────────────────────────────

    @commands.hybrid_command(aliases=["mejora", "improve", "goals"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    @app_commands.describe(jugador="Nombre del jugador")
    @app_commands.autocomplete(jugador=player_name_autocomplete)
    async def plan_mejora(self, ctx: commands.Context, jugador: str = None):
        """Genera un plan de mejora personalizado para un jugador."""
        if not jugador:
            await ctx.send(
                "❗ Por favor, proporciona un nombre de jugador. "
                "Ejemplo: `-mejora W4RR10R`."
            )
            return

        await ctx.defer()

        try:
            data = await self.fetcher.fetch_all_players()
        except Exception as e:
            await ctx.send("❌ Error al conectar con la base de datos. Inténtalo más tarde.")
            logger.error("Error fetching all players: %s", e)
            return

        # Sort by Performance Score
        jugadores_ordenados = sorted(
            data, key=lambda x: x.get("Performance Score", 0), reverse=True
        )

        # Find the player and their rank
        jugador_encontrado = find_player(jugadores_ordenados, jugador)
        ranking = None
        if jugador_encontrado:
            jugador_lower = jugador_encontrado["Player"].lower()
            for i, entry in enumerate(jugadores_ordenados):
                if entry["Player"].lower() == jugador_lower:
                    ranking = i + 1
                    break

        if not jugador_encontrado:
            await ctx.send(f"⚠️ Jugador '{jugador}' no encontrado. Probá `-buscar <nombre>` para verificar.")
            return

        total_players = len(jugadores_ordenados)
        ps = jugador_encontrado.get("Performance Score", 0)
        kd = jugador_encontrado.get("K/D Ratio", 0)
        kpr = jugador_encontrado.get("Kills per Round", 0)
        spr = jugador_encontrado.get("Score per Round", 0)
        rounds_played = jugador_encontrado.get("Rounds", 1)
        total_deaths = jugador_encontrado.get("Total Deaths", 0)
        dpr = total_deaths / rounds_played if rounds_played > 0 else 0

        # ── Edge case: player is #1 ──────────────────────────────────────
        if ranking == 1:
            embed = discord.Embed(
                title=f"🎯 Plan de Mejora para {jugador}",
                description=(
                    f"{tier_badge(ps)}\n"
                    f"Ranking actual: **#1** de {total_players} jugadores\n\n"
                    "🏆 **¡Ya sos el #1!** No hay jugadores por encima tuyo.\n"
                    "Seguí manteniendo tu nivel y liderando el ranking."
                ),
                color=performance_color(ps),
            )
            embed.set_thumbnail(url=BOT_THUMBNAIL)
            embed.set_footer(text=standard_footer(jugador_encontrado))
            await ctx.send(embed=embed)
            return

        # ── Target aspiracional: una banda ~15% MÁS ARRIBA en el ranking (no los 10 de
        # al lado, cuyo promedio ya solés superar — por eso a veces no daba plan). Así
        # siempre hay metas concretas hasta estar cerca del #1.
        player_index = ranking - 1  # 0-based index
        goal_index = max(0, int(player_index * 0.85) - 1)  # ~15% más arriba
        target_group = jugadores_ordenados[max(0, goal_index - 7): goal_index + 8]
        if not target_group:
            target_group = jugadores_ordenados[:15]
        if not target_group:
            await ctx.send("⚠️ No hay suficientes datos para generar un plan de mejora.")
            return

        target_rank = goal_index + 1  # rank objetivo

        # ── Calculate target averages ─────────────────────────────────────
        def avg(key, players):
            vals = [p.get(key, 0) for p in players]
            return sum(vals) / len(vals) if vals else 0

        def avg_dpr(players):
            vals = []
            for p in players:
                td = p.get("Total Deaths", 0)
                rds = p.get("Rounds", 1)
                vals.append(td / rds if rds > 0 else 0)
            return sum(vals) / len(vals) if vals else 0

        target_kd = avg("K/D Ratio", target_group)
        target_kpr = avg("Kills per Round", target_group)
        target_spr = avg("Score per Round", target_group)
        target_rounds = avg("Rounds", target_group)
        target_dpr = avg_dpr(target_group)

        # ── Calculate gaps (only where improvement is needed) ─────────────
        gaps = []

        # K/D gap (higher is better) — only if target is better than player
        if target_kd > kd:
            kd_gap = (target_kd - kd) / kd if kd > 0 else 1.0
            gaps.append(("K/D", kd_gap, kd, target_kd, True))

        # Kills/Round gap (higher is better) — only if target is better
        if target_kpr > kpr:
            kpr_gap = (target_kpr - kpr) / kpr if kpr > 0 else 1.0
            gaps.append(("Kills/Ronda", kpr_gap, kpr, target_kpr, True))

        # Deaths/Round gap (lower is better) — only if target is better (lower)
        if target_dpr < dpr:
            dpr_gap = (dpr - target_dpr) / dpr if dpr > 0 else 0.0
            gaps.append(("Muertes/Ronda", dpr_gap, dpr, target_dpr, False))

        # Score/Round gap (higher is better) — only if target is better
        if target_spr > spr:
            spr_gap = (target_spr - spr) / spr if spr > 0 else 1.0
            gaps.append(("Score/Ronda", spr_gap, spr, target_spr, True))

        # Rounds gap (higher is better) — only if target has more
        if target_rounds > rounds_played:
            rounds_gap = (target_rounds - rounds_played) / rounds_played if rounds_played > 0 else 1.0
            gaps.append(("Rondas Jugadas", rounds_gap, rounds_played, target_rounds, True))

        # ── Metas de DEMOS (integradas): métricas de juego vs el promedio de quienes
        # tienen data de demos. Solo si el jugador tiene esa data (rondas nuevas).
        demo_data = None
        demo_player = None
        try:
            demo_data = await self.fetcher.fetch_player_details()
            demo_player = find_player(demo_data, jugador_encontrado["Player"], key="ign") if demo_data else None
        except Exception:
            demo_player = None
        if demo_player and demo_data:
            def _alive_pct(p):
                a, pl = p.get("alive_seconds", 0), p.get("played_seconds", 0)
                return (a / pl) if (a and pl) else None

            def _kpm(p):
                a, k = p.get("alive_seconds", 0), p.get("total_kills", 0)
                return (k / (a / 60)) if a else None

            def _squad(p):
                rs, rws = p.get("rounds_in_squad", 0), p.get("rounds_with_squad_data", 0)
                return (rs / rws) if rws else None

            def _baseline(fn):
                vals = [v for v in (fn(q) for q in demo_data) if v is not None]
                return (sum(vals) / len(vals)) if vals else None

            for label, fn in (("Tiempo vivo", _alive_pct), ("Kills/min", _kpm),
                              ("Juego en escuadra", _squad)):
                pv, base = fn(demo_player), _baseline(fn)
                if pv is not None and base and pv < base:
                    gaps.append((label, (base - pv) / base, pv, base, True))

        if not gaps:
            # Player is already better than target group in all metrics
            embed = discord.Embed(
                title=f"🎯 Plan de Mejora para {jugador}",
                description=(
                    f"{tier_badge(ps)}\n"
                    f"Ranking actual: **#{ranking}** de {total_players} jugadores\n\n"
                    "✅ **Ya superás al grupo objetivo en todas las métricas.**\n"
                    "Seguí manteniendo tu nivel para escalar en el ranking."
                ),
                color=performance_color(ps),
            )
            embed.set_thumbnail(url=BOT_THUMBNAIL)
            embed.set_footer(text=standard_footer(jugador_encontrado))
            await ctx.send(embed=embed)
            return

        # ── Top 3 biggest gaps ────────────────────────────────────────────
        top_gaps = sorted(gaps, key=lambda x: abs(x[1]), reverse=True)[:3]

        metas_lines = []
        medal_emojis = ["1️⃣", "2️⃣", "3️⃣"]
        weakness_categories = []

        _PCT_METRICS = ("Tiempo vivo", "Juego en escuadra")  # se muestran como porcentaje
        for i, (name, gap_val, player_val, target_val, higher_better) in enumerate(top_gaps):
            medal = medal_emojis[i]
            if higher_better:
                if name == "Rondas Jugadas":
                    metas_lines.append(
                        f"{medal} **Jugar {int(target_val - player_val)} rondas más** para ganar experiencia"
                    )
                elif name in _PCT_METRICS:
                    metas_lines.append(
                        f"{medal} **Subir {name}** de `{player_val:.0%}` a `{target_val:.0%}`"
                    )
                elif name == "Kills/min":
                    metas_lines.append(
                        f"{medal} **Subir Kills/min** de `{player_val:.2f}` a `{target_val:.2f}`"
                    )
                else:
                    metas_lines.append(
                        f"{medal} **Subir {name}** de `{player_val:.2f}` a `{target_val:.2f}` (+{abs(gap_val) * 100:.1f}%)"
                    )
            else:
                metas_lines.append(
                    f"{medal} **Reducir {name}** de `{player_val:.2f}` a `{target_val:.2f}` (-{abs(gap_val) * 100:.1f}%)"
                )

            # Categorize weakness (para elegir consejos)
            if name in ("K/D", "Kills/Ronda", "Kills/min"):
                weakness_categories.append("combat")
            elif name in ("Muertes/Ronda", "Tiempo vivo"):
                weakness_categories.append("survival")
            elif name in ("Score/Ronda", "Juego en escuadra"):
                weakness_categories.append("objective")
            elif name == "Rondas Jugadas":
                weakness_categories.append("experience")

        # ── Identify bottleneck ───────────────────────────────────────────
        norm_components = {
            "K/D": jugador_encontrado.get("Normalized_KD", 0),
            "Score/Ronda": jugador_encontrado.get("Normalized_Score", 0),
            "Kills/Ronda": jugador_encontrado.get("Normalized_Kills_Per_Round", 0),
            "Experiencia": jugador_encontrado.get("Normalized_Rounds", 0),
        }
        bottleneck_name = min(norm_components, key=norm_components.get)
        bottleneck_value = norm_components[bottleneck_name]

        # ── Estimate new Performance Score & ranking ──────────────────────
        # Simulate what happens if the player reaches their target values
        # Use the REAL scoring formula from scraper/scoring.py:
        #   weights: kd=1.0, score=0.4, kpr=0.4, rounds=0.2
        #   caps: kd=5.0, spr=500.0, kpr=10.0, rounds=1000.0
        #   penalty: sigmoid centered at 25 rounds

        sim_kd = kd
        sim_kpr = kpr
        sim_spr = spr
        sim_rounds = rounds_played

        for name, _gap_val, _pv, target_val, higher_better in top_gaps:
            if name == "K/D":
                sim_kd = target_val
            elif name == "Kills/Ronda":
                sim_kpr = target_val
            elif name == "Score/Ronda":
                sim_spr = target_val
            elif name == "Muertes/Ronda":
                # Better K/D from fewer deaths (same kills)
                sim_kd = max(sim_kd, jugador_encontrado.get("Total Kills", 0) / max(target_val * sim_rounds, 1))
            elif name == "Rondas Jugadas":
                sim_rounds = target_val

        # Apply real formula
        norm_kd = min(sim_kd / 5.0, 1.0)
        norm_spr = min(sim_spr / 500.0, 1.0)
        norm_kpr = min(sim_kpr / 10.0, 1.0)
        norm_rounds = min(sim_rounds / 1000.0, 1.0)

        raw_score = 1.0 * norm_kd + 0.4 * norm_spr + 0.4 * norm_kpr + 0.2 * norm_rounds

        # Sigmoid penalty
        sigmoid = 1.0 / (1.0 + math.exp(-((sim_rounds - 25) / 10)))
        estimated_ps = raw_score * sigmoid

        # Floor: never estimate worse than current
        estimated_ps = max(estimated_ps, ps + 0.01)

        estimated_rank = sum(
            1 for p in jugadores_ordenados if p.get("Performance Score", 0) > estimated_ps
        ) + 1
        rank_gain = ranking - estimated_rank

        # ── Pick contextual tips from tips.json ───────────────────────────
        tips_path = Path(__file__).parent.parent / "data" / "tips.json"
        try:
            with open(tips_path, encoding="utf-8") as f:
                tips_data = json.load(f)
        except Exception:
            tips_data = {"general": [], "kits": {}}

        selected_tips = []

        # Use dedicated improvement tips when available, fall back to keyword search on general
        improvement_tips = tips_data.get("improvement", {})
        weakness_to_improvement = {
            "survival": "survival",
            "combat": "combat",
            "objective": "objectives",
            "experience": "experience",
        }

        for wcat in weakness_categories:
            imp_key = weakness_to_improvement.get(wcat)
            imp_tips = improvement_tips.get(imp_key, []) if imp_key else []
            if imp_tips:
                random.shuffle(imp_tips)
                selected_tips.extend(imp_tips[:2])
            else:
                # Fallback: keyword search on general tips
                kw_map = {
                    "survival": ["cobertura", "cúbrete", "campo abierto", "proteg", "superviv"],
                    "combat": ["apunta", "precisión", "ráfaga", "dispara", "flanque"],
                    "objective": ["objetivo", "fob", "suministro", "construy", "coordin"],
                    "experience": ["practica", "entrena", "reflexion", "aprend"],
                }
                keywords = kw_map.get(wcat, [])
                for tip in tips_data.get("general", []):
                    if any(kw in tip.lower() for kw in keywords):
                        selected_tips.append(tip)

        # Deduplicate and pick 2-3
        seen = set()
        unique_tips = []
        for tip in selected_tips:
            if tip not in seen:
                seen.add(tip)
                unique_tips.append(tip)

        if len(unique_tips) < 2:
            general_tips = list(tips_data.get("general", []))
            random.shuffle(general_tips)
            for tip in general_tips:
                if tip not in seen:
                    unique_tips.append(tip)
                    seen.add(tip)
                if len(unique_tips) >= 3:
                    break

        final_tips = unique_tips[:3]

        # ── Determine next tier badge ─────────────────────────────────────
        current_badge = tier_badge(ps)
        next_badge = tier_badge(min(ps + 0.20, 1.0))

        # ── Build the embed ───────────────────────────────────────────────
        color = performance_color(ps)
        embed = discord.Embed(
            title=f"🎯 Plan de Mejora para {jugador}",
            description=(
                f"{current_badge} → Meta: {next_badge}\n"
                f"Ranking actual: **#{ranking}** · Objetivo: **top {target_rank}**"
            ),
            color=color,
        )
        embed.set_thumbnail(url=BOT_THUMBNAIL)

        penalty_info = sigmoid_penalty_display(rounds_played)
        situacion_value = (
            f"**Performance Score:** `{ps:.2f}`\n"
            f"**Cuello de botella:** {bottleneck_name} (`{bottleneck_value:.2f}`)"
        )
        if penalty_info:
            situacion_value += f"\n{penalty_info}"

        embed.add_field(
            name="📊 Tu Situación Actual",
            value=situacion_value,
            inline=False,
        )

        embed.add_field(
            name="🎯 Metas de Mejora",
            value="\n".join(metas_lines),
            inline=False,
        )

        if final_tips:
            tips_text = "\n".join(f"• {tip}" for tip in final_tips)
            embed.add_field(
                name="💡 Consejos Personalizados",
                value=tips_text,
                inline=False,
            )

        embed.add_field(
            name="📈 Impacto Estimado",
            value=(
                f"Si alcanzás estas metas:\n"
                f"├─ **Performance Score:** `{ps:.2f}` → ~`{estimated_ps:.2f}`\n"
                f"└─ **Ranking estimado:** #{ranking} → ~#{estimated_rank} "
                f"({'↑ ' + str(rank_gain) + ' posiciones' if rank_gain > 0 else 'mantener posición'})"
            ),
            inline=False,
        )

        # ── Consejos cualitativos de demos (reusa el demo_player ya traído) ──────
        demo_suggestions = []
        if demo_player:
            tw_ratio = demo_player.get("teamwork_ratio", 0)
            medic_rounds = demo_player.get("rounds_as_medic", 0)
            kits = demo_player.get("kits_used", {})
            top_kit_raw = max(kits, key=kits.get) if kits else None
            top_kit_display = get_kit_display(top_kit_raw) if top_kit_raw else None
            is_medic = top_kit_raw and "medic" in top_kit_raw.lower()
            revives_round = demo_player.get("total_revives_given", 0) / max(
                medic_rounds or demo_player.get("rounds_played", 1), 1)

            if tw_ratio and tw_ratio < 0.20:
                demo_suggestions.append(
                    f"🤝 Tu teamwork ratio es bajo ({tw_ratio:.0%}). "
                    "Probá jugar medic o capturar flags para subir tu score."
                )
            if is_medic and medic_rounds and revives_round < 1.5:
                demo_suggestions.append(
                    f"💉 Jugás medic pero reviveás poco ({revives_round:.1f}/ronda de médico). "
                    "Priorizá revivir compañeros caídos."
                )
            if demo_player.get("total_teamkills", 0) >= 10:
                demo_suggestions.append(
                    f"🛡️ Cuidado con los teamkills ({demo_player['total_teamkills']}). "
                    "Identificá bien a aliados antes de disparar."
                )
            if top_kit_display:
                demo_suggestions.append(
                    f"🎖️ Tu kit principal es **{top_kit_display}**. "
                    "Especializarte en un rol mejora tu consistencia."
                )

        if demo_suggestions:
            embed.add_field(
                name="🎬 Sugerencias de Demos",
                value="\n".join(demo_suggestions[:3]),
                inline=False,
            )

        embed.set_footer(text=standard_footer(jugador_encontrado))
        await ctx.send(embed=embed)

    # ── -rivales <jugador> ─────────────────────────────────────────────────

    @commands.hybrid_command(aliases=["rivals", "similares"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    @app_commands.describe(jugador="Nombre del jugador")
    @app_commands.autocomplete(jugador=player_name_autocomplete)
    async def rivales(self, ctx: commands.Context, jugador: str = None):
        """Encuentra jugadores con perfil similar al tuyo."""
        if not jugador:
            await ctx.send(
                "❗ Por favor, proporciona un nombre de jugador. "
                "Ejemplo: `-rivales W4RR10R`."
            )
            return

        await ctx.defer()

        try:
            data = await self.fetcher.fetch_all_players()
        except Exception as e:
            await ctx.send("❌ Error al conectar con la base de datos. Inténtalo más tarde.")
            logger.error("Error fetching all players: %s", e)
            return

        jugador_encontrado = find_player(data, jugador)
        if not jugador_encontrado:
            await ctx.send(f"⚠️ Jugador '{jugador}' no encontrado. Probá `-buscar <nombre>` para verificar.")
            return

        target_radar = get_player_radar(jugador_encontrado)
        if not target_radar:
            await ctx.send(f"⚠️ No hay datos suficientes de radar para **{jugador_encontrado['Player']}**.")
            return

        radar_keys = ["letalidad", "supervivencia", "teamwork", "impacto", "consistencia", "versatilidad"]

        def radar_distance(r1: dict, r2: dict) -> float:
            return math.sqrt(sum((r1.get(k, 0) - r2.get(k, 0)) ** 2 for k in radar_keys))

        candidates = []
        for p in data:
            if p["Player"].lower() == jugador_encontrado["Player"].lower():
                continue
            p_radar = get_player_radar(p)
            if not p_radar or p.get("Rounds", 0) < 50:
                continue
            dist = radar_distance(target_radar, p_radar)
            candidates.append((p, dist))

        if not candidates:
            await ctx.send("⚠️ No se encontraron jugadores con datos suficientes para comparar.")
            return

        candidates.sort(key=lambda x: x[1])
        top5 = candidates[:5]

        max_possible_dist = math.sqrt(6)

        try:
            tier_config = await self.fetcher.fetch_tier_config()
        except Exception:
            tier_config = None
        thresholds = tier_config.get("thresholds") if isinstance(tier_config, dict) else None

        ps_target = jugador_encontrado.get("Performance Score", 0)
        color = performance_color(ps_target, thresholds)

        medal_emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        lines = []
        for i, (p, dist) in enumerate(top5):
            similarity = max(0, (1 - dist / max_possible_dist)) * 100
            ps_val = p.get("Performance Score", 0)
            p_clan = p.get("Clan", "N/A")
            clan_emoji = get_clan_emoji(p_clan)
            badge = tier_badge(ps_val, thresholds)
            lines.append(
                f"{medal_emojis[i]} **{p['Player']}** ({clan_emoji}{p_clan}) — "
                f"{similarity:.0f}% similitud · PS: {ps_val:.2f} {badge}"
            )

        target_name = jugador_encontrado["Player"]
        target_badge = tier_badge(ps_target, thresholds)
        clan_target = jugador_encontrado.get("Clan", "N/A")

        embed = discord.Embed(
            title=f"🎯 Rivales de {target_name} (perfil similar)",
            description=f"{target_badge} · PS: {ps_target:.2f} · Clan: {clan_target}\n\n" + "\n".join(lines),
            color=color,
        )
        embed.set_thumbnail(url=clan_logo_url(clan_target))
        embed.set_footer(text=standard_footer(jugador_encontrado))
        await ctx.send(embed=embed)

    # ── -clan_roster <clan> ────────────────────────────────────────────────

    @commands.hybrid_command(aliases=["roster", "plantel"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    @app_commands.describe(clan="Nombre del clan")
    async def clan_roster(self, ctx: commands.Context, clan: str = None):
        """Muestra el plantel del clan organizado por rol/arquetipo."""
        if not clan:
            await ctx.send(
                "❗ Por favor, proporciona un nombre de clan. "
                "Ejemplo: `-clan_roster LDH`."
            )
            return

        await ctx.defer()

        try:
            data = await self.fetcher.fetch_all_players()
        except Exception as e:
            await ctx.send("❌ Error al conectar con la base de datos. Inténtalo más tarde.")
            logger.error("Error fetching all players: %s", e)
            return

        clan_upper = clan.upper()
        clan_players = [
            p for p in data
            if p.get("Clan", "").upper() == clan_upper
        ]

        if not clan_players:
            await ctx.send(f"⚠️ No se encontraron jugadores del clan **{clan}**.")
            return

        # Determine actual clan name from first match
        actual_clan = clan_players[0].get("Clan", clan)

        # Group by archetype
        archetype_groups: dict[str, list[dict]] = {}
        for p in clan_players:
            arch = p.get("archetype", {})
            arch_name = arch.get("name", "Soldado") if isinstance(arch, dict) else "Soldado"
            archetype_groups.setdefault(arch_name, []).append(p)

        # Sort each group by PS descending
        for group in archetype_groups.values():
            group.sort(key=lambda x: x.get("Performance Score", 0), reverse=True)

        # Priority order for archetypes
        archetype_priority = [
            "Médico", "Oficial", "Tanquista", "Demoledor", "Francotirador",
            "Estratega", "Explorador", "Soldado",
        ]
        archetype_emojis = {
            "Médico": "💉",
            "Oficial": "📡",
            "Tanquista": "🛡️",
            "Demoledor": "💣",
            "Francotirador": "🎯",
            "Estratega": "🧠",
            "Explorador": "🔭",
            "Soldado": "⚔️",
        }

        # Sort groups by priority (unknown archetypes go last)
        sorted_archetypes = sorted(
            archetype_groups.keys(),
            key=lambda a: archetype_priority.index(a) if a in archetype_priority else len(archetype_priority),
        )

        try:
            tier_config = await self.fetcher.fetch_tier_config()
        except Exception:
            tier_config = None
        thresholds = tier_config.get("thresholds") if isinstance(tier_config, dict) else None

        clan_emoji = get_clan_emoji(actual_clan)
        embed = discord.Embed(
            title=f"📋 Plantel de {clan_emoji}{actual_clan} ({len(clan_players)} jugadores)",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=clan_logo_url(actual_clan))

        for arch_name in sorted_archetypes:
            players = archetype_groups[arch_name]
            emoji = archetype_emojis.get(arch_name, "⚔️")
            player_strs = [
                f"{p['Player']} ({p.get('Performance Score', 0):.2f})"
                for p in players
            ]
            embed.add_field(
                name=f"{emoji} {arch_name}s ({len(players)})",
                value=" · ".join(player_strs) if player_strs else "—",
                inline=False,
            )

        # Warning for missing key roles
        key_roles = ["Médico", "Oficial"]
        missing_roles = [r for r in key_roles if r not in archetype_groups]
        if missing_roles:
            warnings = "\n".join(
                f"⚠️ Sin {role}s — consideren reclutar uno"
                for role in missing_roles
            )
            embed.add_field(name="⚠️ Roles Faltantes", value=warnings, inline=False)

        # Use standard_footer from first player sorted by PS
        best_player = max(clan_players, key=lambda x: x.get("Performance Score", 0))
        embed.set_footer(text=standard_footer(best_player))
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Stats(bot))
