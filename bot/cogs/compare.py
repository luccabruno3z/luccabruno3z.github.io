"""Compare cog -- compare, analizar_equipo, sugerir_equipo, comparar_equipos, prediccion."""

import logging

import discord
from discord.ext import commands
from discord import app_commands

from bot.config import (
    BOT_THUMBNAIL,
    json_url,
    performance_color,
)
from bot.services.clan_registry import clan_choices
from bot.services.chart_renderer import render_kd_chart, render_comparison_chart, render_multi_comparison, render_radar_chart, render_horizontal_bars, render_comparison_bars, render_probability_bar
from bot.utils import format_number, find_player, versus_table, progress_bar, relative_time, sample_reliability, standard_footer, ERR_DB
from bot.views.demo_details import DemoDetailsView
from bot.ui.comparison_card import ComparisonCard

logger = logging.getLogger(__name__)


# ── Interactive views for compare cog ────────────────────────────────────────


class InvertCompareView(discord.ui.View):
    """Button to swap the two entities in a compare result."""

    def __init__(self, cog, ctx, entity1: str, entity2: str, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.entity1 = entity1
        self.entity2 = entity2

    @discord.ui.button(label="Invertir", style=discord.ButtonStyle.secondary, emoji="\U0001f500")
    async def invert_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        # Re-invoke the compare command with swapped arguments
        swapped_e1, swapped_e2 = self.entity2, self.entity1
        await self.cog.compare(self.ctx, swapped_e1, swapped_e2)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True  # type: ignore[union-attr]


class OtraSugerenciaView(discord.ui.View):
    """Button to show the next-best team suggestion (offset by num_jugadores)."""

    def __init__(self, cog, ctx, clan: str, num_jugadores: int, offset: int, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.clan = clan
        self.num_jugadores = num_jugadores
        self.offset = offset

    @discord.ui.button(label="Otra sugerencia", style=discord.ButtonStyle.primary, emoji="\U0001f504")
    async def next_suggestion(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        await self.cog._send_sugerencia(self.ctx, self.clan, self.num_jugadores, self.offset)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True  # type: ignore[union-attr]


# ── Autocomplete helpers ───────────────────────────────────────────────────

async def player_name_autocomplete(
    interaction: discord.Interaction, current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete for player names."""
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


# ── Autocomplete de clan (data-driven desde bot.clans) ──────────────────────
# Antes eran choices estáticos (limitados a 25); con >25 clanes usamos autocomplete.

async def clan_autocomplete(
    interaction: discord.Interaction, current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete de clanes para -sugerir_equipo y -compare_tops."""
    return clan_choices(interaction.client, current)


class Compare(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def fetcher(self):
        return self.bot.data_fetcher

    # ── -compare <entity1> <entity2> ──────────────────────────────────────

    @commands.hybrid_command(aliases=["comparar", "vs", "versus", "comp"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    @app_commands.describe(
        entity1="Primer jugador o clan",
        entity2="Segundo jugador o clan",
    )
    @app_commands.autocomplete(entity1=player_name_autocomplete, entity2=player_name_autocomplete)
    async def compare(self, ctx: commands.Context, entity1: str = None, entity2: str = None):
        """Compara las estadísticas de dos jugadores o clanes."""
        if not entity1 or not entity2:
            await ctx.send(
                "❗ Uso: `-compare <jugador1|clan1> <jugador2|clan2>`."
            )
            return

        try:
            data_players = await self.fetcher.fetch_all_players()
        except Exception as e:
            await ctx.send(ERR_DB)
            logger.error("Error: %s", e)
            return

        # Check if both inputs are clan names — go directly to clan comparison
        all_clan_names = {p.get("Clan", "") for p in data_players if p.get("Clan")}
        entity1_is_clan = entity1 in all_clan_names or entity1.upper() in {c.upper() for c in all_clan_names}
        entity2_is_clan = entity2 in all_clan_names or entity2.upper() in {c.upper() for c in all_clan_names}

        if entity1_is_clan and entity2_is_clan:
            # Resolve correct clan names (case-insensitive)
            clan1 = next((c for c in all_clan_names if c.upper() == entity1.upper()), entity1)
            clan2 = next((c for c in all_clan_names if c.upper() == entity2.upper()), entity2)
            # Jump to clan comparison using resolved clan names
            entity1 = clan1
            entity2 = clan2
            p1 = None
            p2 = None
        else:
            p1 = find_player(data_players, entity1)
            p2 = find_player(data_players, entity2)

        # Mixed input: one is a player, other is a clan → player vs clan average
        if (p1 and not p2) or (p2 and not p1):
            non_player = entity2 if (p1 and not p2) else entity1
            is_clan = any(p.get("Clan", "").upper() == non_player.upper() for p in data_players)
            if not is_clan:
                await ctx.send(
                    f"⚠️ No se encontró al jugador ni clan '{non_player}'. "
                    "Probá `-buscar <nombre>` para verificar."
                )
                return

            # Player vs Clan average comparison
            the_player = p1 if p1 else p2
            player_name = entity1 if p1 else entity2
            clan_name_resolved = next(
                (p.get("Clan", "") for p in data_players if p.get("Clan", "").upper() == non_player.upper()),
                non_player,
            )
            clan_members = [p for p in data_players if p.get("Clan", "") == clan_name_resolved]
            if not clan_members:
                await ctx.send(f"⚠️ No se encontraron miembros del clan '{non_player}'.")
                return

            n = len(clan_members)
            # Solo métricas de all_players (universales): las de demos NO van acá
            # porque no todos los miembros tienen datos de demos y el promedio
            # quedaría sesgado/incomparable.
            clan_avg = {
                "K/D Ratio": sum(p.get("K/D Ratio", 0) for p in clan_members) / n,
                "Kills per Round": sum(p.get("Kills per Round", 0) for p in clan_members) / n,
                "Deaths per Round": sum(p.get("Deaths per Round", 0) for p in clan_members) / n,
                "Score per Round": sum(p.get("Score per Round", 0) for p in clan_members) / n,
                "Performance Score": sum(p.get("Performance Score", 0) for p in clan_members) / n,
                "Activity Index": sum(p.get("Activity Index", 0) for p in clan_members) / n,
                "Rounds": sum(p.get("Rounds", 0) for p in clan_members) / n,
                "Total Kills": sum(p.get("Total Kills", 0) for p in clan_members) / n,
                "Total Score": sum(p.get("Total Score", 0) for p in clan_members) / n,
            }

            metrics = [
                ("K/D", the_player["K/D Ratio"], clan_avg["K/D Ratio"], True),
                ("Kills/Ronda", the_player.get("Kills per Round", 0), clan_avg["Kills per Round"], True),
                ("Deaths/Ronda", the_player.get("Deaths per Round", 0), clan_avg["Deaths per Round"], False),
                ("Score/Ronda", the_player.get("Score per Round", 0), clan_avg["Score per Round"], True),
                ("Performance", the_player.get("Performance Score", 0), clan_avg["Performance Score"], True),
                ("Actividad", the_player.get("Activity Index", 0), clan_avg["Activity Index"], True),
                ("Rondas", the_player.get("Rounds", 0), clan_avg["Rounds"], True),
            ]
            table, p_wins, c_wins, _ties = versus_table(player_name, f"x̄ {clan_name_resolved}", metrics)

            if p_wins > c_wins:
                verdict = f"**{player_name}** supera al promedio de **{clan_name_resolved}**"
            elif c_wins > p_wins:
                verdict = f"**{player_name}** está por debajo del promedio de **{clan_name_resolved}**"
            else:
                verdict = f"**{player_name}** está al nivel del promedio de **{clan_name_resolved}**"

            embed = discord.Embed(
                title=f"🔍 {player_name} vs {clan_name_resolved} (promedio)",
                description=f"**{player_name}** ⚔️ **Promedio de {clan_name_resolved}** ({n} miembros)",
                color=discord.Color.teal(),
            )
            embed.add_field(name="📊 Comparación (▲ = mejor)", value=table, inline=False)
            embed.add_field(name="🏆 Veredicto", value=verdict, inline=False)

            chart_labels = ["K/D", "Kills/R", "Score/R", "Performance", "Rounds"]
            vals1 = [the_player["K/D Ratio"], the_player.get("Kills per Round", 0), the_player.get("Score per Round", 0),
                     the_player.get("Performance Score", 0), the_player.get("Rounds", 0)]
            vals2 = [clan_avg["K/D Ratio"], clan_avg["Kills per Round"], clan_avg["Score per Round"],
                     clan_avg["Performance Score"], clan_avg["Rounds"]]
            chart_buf = render_multi_comparison(player_name, vals1, f"Avg {clan_name_resolved}", vals2, chart_labels, f"{player_name} vs {clan_name_resolved}")
            file = discord.File(chart_buf, filename="compare_player_clan.png")
            embed.set_image(url="attachment://compare_player_clan.png")
            embed.set_footer(text=standard_footer(the_player))

            await ctx.send(embed=embed, file=file)
            return

        if p1 and p2:
            # Player vs Player — tabla alineada (una ▲ por fila, sin ruido de emojis)
            metrics = [
                ("K/D", p1["K/D Ratio"], p2["K/D Ratio"], True),
                ("Kills/Ronda", p1.get("Kills per Round", 0), p2.get("Kills per Round", 0), True),
                ("Deaths/Ronda", p1.get("Deaths per Round", 0), p2.get("Deaths per Round", 0), False),
                ("Score/Ronda", p1.get("Score per Round", 0), p2.get("Score per Round", 0), True),
                ("Performance", p1.get("Performance Score", 0), p2.get("Performance Score", 0), True),
                ("Actividad", p1.get("Activity Index", 0), p2.get("Activity Index", 0), True),
                ("Rondas", p1.get("Rounds", 0), p2.get("Rounds", 0), True),
                ("Total Kills", p1.get("Total Kills", 0), p2.get("Total Kills", 0), True),
                ("Total Score", p1.get("Total Score", 0), p2.get("Total Score", 0), True),
            ]
            table, p1_wins, p2_wins, _ties = versus_table(entity1, entity2, metrics)

            # Bloque extra de demos: SOLO jugador-vs-jugador y SOLO si ambos tienen
            # >=5 rondas de demos (cobertura parcial: ~1 de cada 3 jugadores). No
            # cuenta para el veredicto, así el resultado no depende de si hay demos.
            demo_table = demo_note = None
            try:
                demo_data = await self.fetcher.fetch_player_details()
            except Exception:
                demo_data = None
            if isinstance(demo_data, list):
                d1 = find_player(demo_data, entity1, key="ign")
                d2 = find_player(demo_data, entity2, key="ign")
                if d1 and d2 and d1.get("rounds_played", 0) >= 5 and d2.get("rounds_played", 0) >= 5:
                    def _rate(d, key):
                        return d.get(key, 0) / max(d.get("rounds_played", 1), 1)

                    def _wr(d):
                        decided = d.get("wins", 0) + d.get("losses", 0)
                        return d.get("wins", 0) / decided * 100 if decided else 0.0

                    demo_metrics = [
                        ("Winrate %", _wr(d1), _wr(d2), True),
                        ("Revives/R", _rate(d1, "total_revives_given"), _rate(d2, "total_revives_given"), True),
                        ("Vehic.dest/R", _rate(d1, "total_vehicles_destroyed"), _rate(d2, "total_vehicles_destroyed"), True),
                        ("Banderas/R", _rate(d1, "total_flags_captured"), _rate(d2, "total_flags_captured"), True),
                        ("TKs/R", _rate(d1, "total_teamkills"), _rate(d2, "total_teamkills"), False),
                        ("Mejor racha", d1.get("best_killstreak", 0), d2.get("best_killstreak", 0), True),
                    ]
                    demo_table, dw1, dw2, _ = versus_table(entity1, entity2, demo_metrics)
                    demo_note = (
                        f"📼 Demos ({d1['rounds_played']}R vs {d2['rounds_played']}R): "
                        f"{entity1} **{dw1}** · {entity2} **{dw2}** — no cuenta para el veredicto"
                    )

            if p1_wins > p2_wins:
                summary = f"🏆 **{entity1}** gana **{p1_wins}/{len(metrics)}** categorías"
            elif p2_wins > p1_wins:
                summary = f"🏆 **{entity2}** gana **{p2_wins}/{len(metrics)}** categorías"
            else:
                summary = f"🤝 Empate: **{p1_wins}/{len(metrics)}** categorías cada uno"

            p1_rounds = p1.get("Rounds", 0)
            p2_rounds = p2.get("Rounds", 0)
            warning = None
            if p1_rounds < 50 or p2_rounds < 50:
                warning = (
                    (f"{entity1} tiene solo {p1_rounds} rondas. " if p1_rounds < 50 else "")
                    + (f"{entity2} tiene solo {p2_rounds} rondas. " if p2_rounds < 50 else "")
                    + "Stats con pocas rondas pueden no ser representativos."
                )

            mode = self.bot.guild_settings.get_mode(ctx.guild.id) if ctx.guild else "combined"
            demo_for = [entity1, entity2] if mode in ("combined", "demos") else None

            # Radar dentro de la misma tarjeta (antes iba como segundo mensaje/embed).
            radar_file = None
            radar1, radar2 = p1.get("radar"), p2.get("radar")
            if radar1 and radar2:
                radar_labels = ["Letalidad", "Supervivencia", "Teamwork", "Impacto", "Consistencia", "Versatilidad"]
                radar_keys = ["letalidad", "supervivencia", "teamwork", "impacto", "consistencia", "versatilidad"]
                p1_values = {label: radar1.get(key, 0) for label, key in zip(radar_labels, radar_keys)}
                p2_values = {label: radar2.get(key, 0) for label, key in zip(radar_labels, radar_keys)}
                radar_buf = render_radar_chart(p1_values, p2_values, p1["Player"], p2["Player"])
                radar_file = discord.File(radar_buf, filename="radar_vs.png")

            card = ComparisonCard(
                self, ctx, entity1, entity2,
                table=table, summary=summary, warning=warning,
                footer=standard_footer(p1), demo_for=demo_for,
                radar_filename="radar_vs.png" if radar_file else None,
                demo_table=demo_table, demo_note=demo_note,
            )
            if radar_file:
                card.message = await ctx.send(view=card, files=[radar_file])
            else:
                card.message = await ctx.send(view=card)

        else:
            # Clan vs Clan comparison — premium format
            def sumar_estadisticas(clan_name):
                total_kills = total_deaths = total_score = total_rounds = 0
                count = 0
                total_ps = 0.0
                total_kd = 0.0
                total_act = 0.0
                for player in data_players:
                    if player.get("Clan", "") == clan_name:
                        total_kills += player.get("Total Kills", 0)
                        total_deaths += player.get("Total Deaths", 0)
                        total_score += player.get("Total Score", 0)
                        total_rounds += player.get("Rounds", 0)
                        total_ps += player.get("Performance Score", 0)
                        total_kd += player.get("K/D Ratio", 0)
                        total_act += player.get("Activity Index", 0)
                        count += 1
                avg_ps = total_ps / count if count else 0
                avg_kd = total_kd / count if count else 0
                avg_act = total_act / count if count else 0
                team_kd = total_kills / total_deaths if total_deaths else 0
                return {
                    "kills": total_kills, "deaths": total_deaths,
                    "score": total_score, "rounds": total_rounds,
                    "members": count, "avg_ps": avg_ps, "avg_kd": avg_kd,
                    "avg_act": avg_act, "team_kd": team_kd,
                }

            s1 = sumar_estadisticas(entity1)
            s2 = sumar_estadisticas(entity2)

            if s1["members"] == 0 and s2["members"] == 0:
                await ctx.send(f"⚠️ No se encontraron jugadores ni clanes con '{entity1}' o '{entity2}'.")
                return
            if s1["members"] == 0:
                await ctx.send(f"⚠️ No se encontraron jugadores en el clan '{entity1}'.")
                return
            if s2["members"] == 0:
                await ctx.send(f"⚠️ No se encontraron jugadores en el clan '{entity2}'.")
                return

            clan_metrics = [
                ("Total Kills", s1["kills"], s2["kills"], True),
                ("Total Deaths", s1["deaths"], s2["deaths"], False),
                ("Total Score", s1["score"], s2["score"], True),
                ("Total Rondas", s1["rounds"], s2["rounds"], True),
                ("Miembros", s1["members"], s2["members"], True),
                ("K/D Equipo", s1["team_kd"], s2["team_kd"], True),
                ("Avg K/D", s1["avg_kd"], s2["avg_kd"], True),
                ("Avg Perf.", s1["avg_ps"], s2["avg_ps"], True),
                ("Avg Activ.", s1["avg_act"], s2["avg_act"], True),
            ]
            table, e1_wins, e2_wins, ties = versus_table(entity1, entity2, clan_metrics)

            if e1_wins > e2_wins:
                winner = entity1
            elif e2_wins > e1_wins:
                winner = entity2
            else:
                winner = None

            summary = (
                f"**Resultado:** {winner} gana {max(e1_wins, e2_wins)}/{len(clan_metrics)} categorías"
                if winner
                else f"**Resultado:** Empate {e1_wins}/{len(clan_metrics)} categorías cada uno"
            )

            embed = discord.Embed(
                title=f"🔍 {entity1} vs {entity2}",
                description=f"**{entity1}** ({s1['members']} miembros) ⚔️ **{entity2}** ({s2['members']} miembros)",
                color=discord.Color.gold(),
            )
            embed.add_field(name="📊 Comparación (▲ = mejor)", value=table, inline=False)
            embed.add_field(name="🏆 Veredicto", value=summary, inline=False)

            # Build clan vs clan chart
            chart_labels = ["Total Kills", "Total Deaths", "Total Score", "Miembros", "K/D Equipo", "Avg K/D", "Avg PS"]
            vals1 = [s1["kills"], s1["deaths"], s1["score"], s1["members"], s1["team_kd"], s1["avg_kd"], s1["avg_ps"]]
            vals2 = [s2["kills"], s2["deaths"], s2["score"], s2["members"], s2["team_kd"], s2["avg_kd"], s2["avg_ps"]]
            chart_buf = render_multi_comparison(entity1, vals1, entity2, vals2, chart_labels, f"{entity1} vs {entity2}")
            file = discord.File(chart_buf, filename="compare_clans.png")
            embed.set_image(url="attachment://compare_clans.png")

            embed.set_footer(text=standard_footer(data_players))
            view = InvertCompareView(self, ctx, entity1, entity2)
            await ctx.send(embed=embed, file=file, view=view)

    # ── -analizar_equipo <jugadores...> ───────────────────────────────────

    @commands.hybrid_command(aliases=["team", "equipo"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    @app_commands.describe(jugadores="Nombres de jugadores separados por espacios")
    async def analizar_equipo(self, ctx: commands.Context, *, jugadores: str = None):
        if not jugadores:
            await ctx.send(
                "❗ Por favor, proporciona entre 2 y 8 jugadores. "
                "Ejemplo: `-analizar_equipo Jugador1 Jugador2 ... JugadorN`."
            )
            return

        nombres_jugadores = jugadores.split()

        if len(nombres_jugadores) < 2 or len(nombres_jugadores) > 8:
            await ctx.send("❗ El equipo debe tener entre 2 y 8 jugadores.")
            return

        await ctx.defer()

        try:
            data = await self.fetcher.fetch_all_players()
        except Exception as e:
            await ctx.send(ERR_DB)
            logger.error("Error: %s", e)
            return

        equipo = []
        for nombre in nombres_jugadores:
            found = find_player(data, nombre)
            if not found:
                await ctx.send(f"⚠️ Jugador '{nombre}' no encontrado. Probá `-buscar <nombre>` para verificar.")
                return
            equipo.append(found)

        total_score = sum(j["Total Score"] for j in equipo)
        total_kills = sum(j["Total Kills"] for j in equipo)
        total_deaths = sum(j["Total Deaths"] for j in equipo)
        total_rounds = sum(j["Rounds"] for j in equipo)
        avg_ps = sum(j["Performance Score"] for j in equipo) / len(equipo)
        avg_kpr = total_kills / total_rounds if total_rounds > 0 else 0
        avg_dpr = total_deaths / total_rounds if total_rounds > 0 else 0
        team_kd = total_kills / total_deaths if total_deaths > 0 else 0

        nombres = [j["Player"] for j in equipo]
        kd_ratios = [j["K/D Ratio"] for j in equipo]

        buf = render_kd_chart(nombres, kd_ratios, "K/D Ratio de Jugadores")

        # K/D progress bar (scale: 0-3.0 as "excellent")
        kd_bar = progress_bar(team_kd, 3.0, 10)

        embed = discord.Embed(
            title="📊 Análisis de Composición de Equipo",
            description=f"Equipo de **{len(equipo)}** jugadores: {', '.join(nombres)}",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=BOT_THUMBNAIL)
        embed.add_field(
            name="⚔️ Rendimiento",
            value=(
                f"💥 **K/D Equipo:** {format_number(team_kd)}\n"
                f"`{kd_bar}`\n"
                f"🌟 **Avg Performance:** {format_number(avg_ps)}\n"
                f"🔫 **Kills/Ronda:** {format_number(avg_kpr)}\n"
                f"💀 **Muertes/Ronda:** {format_number(avg_dpr)}"
            ),
            inline=True,
        )
        embed.add_field(
            name="📈 Totales",
            value=(
                f"☠️ **Kills:** {format_number(total_kills)}\n"
                f"💀 **Muertes:** {format_number(total_deaths)}\n"
                f"🏆 **Score:** {format_number(total_score)}\n"
                f"🎮 **Rondas:** {format_number(total_rounds)}"
            ),
            inline=True,
        )

        file = discord.File(buf, filename="team_analysis.png")
        embed.set_image(url="attachment://team_analysis.png")
        embed.set_footer(text=standard_footer(data))
        await ctx.send(embed=embed, file=file)

    # ── -sugerir_equipo <clan> <num_jugadores> ────────────────────────────

    async def _send_sugerencia(self, ctx: commands.Context, clan: str, num_jugadores: int, offset: int = 0):
        """Internal helper: build and send a team suggestion embed at a given offset."""
        try:
            data = await self.fetcher.fetch_json(json_url(clan))
        except Exception as e:
            await ctx.send(ERR_DB)
            logger.error("Error: %s", e)
            return

        jugadores_ordenados = sorted(
            data,
            key=lambda x: (x.get("Kills per Round", 0), -x.get("Deaths per Round", 0)),
            reverse=True,
        )

        # If offset exceeds available players, wrap around
        if offset >= len(jugadores_ordenados):
            offset = 0

        equipo = jugadores_ordenados[offset : offset + num_jugadores]
        if not equipo:
            await ctx.send("No hay suficientes jugadores para otra sugerencia.")
            return

        total_score = sum(j["Total Score"] for j in equipo)
        total_kills = sum(j["Total Kills"] for j in equipo)
        total_deaths = sum(j["Total Deaths"] for j in equipo)
        total_rounds = sum(j["Rounds"] for j in equipo)
        avg_ps = sum(j["Performance Score"] for j in equipo) / len(equipo)
        avg_kpr = total_kills / total_rounds if total_rounds > 0 else 0
        avg_dpr = total_deaths / total_rounds if total_rounds > 0 else 0
        team_kd = total_kills / total_deaths if total_deaths > 0 else 0

        suggestion_num = (offset // num_jugadores) + 1
        embed = discord.Embed(
            title=f"🎯 Equipo Sugerido para {clan} (#{suggestion_num})",
            description=f"Los **{len(equipo)}** mejores jugadores disponibles del clan **{clan}**:",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=BOT_THUMBNAIL)

        for j in equipo:
            embed.add_field(
                name=f"👤 {j['Player']}",
                value=(
                    f"💥 **K/D:** {format_number(j['K/D Ratio'])}\n"
                    f"🔫 **Kills/Ronda:** {format_number(j['Kills per Round'])}\n"
                    f"💀 **Muertes/Ronda:** {format_number(j['Deaths per Round'])}\n"
                    f"🌟 **Performance:** {format_number(j['Performance Score'])}\n"
                    f"🎮 **Rondas:** {format_number(j['Rounds'])}"
                ),
                inline=True,
            )

        embed.add_field(
            name="📊 Métricas del Equipo",
            value=(
                f"💥 **K/D Equipo:** {format_number(team_kd)}\n"
                f"🌟 **Avg Performance:** {format_number(avg_ps)}\n"
                f"🔫 **Kills/Ronda:** {format_number(avg_kpr)}\n"
                f"💀 **Muertes/Ronda:** {format_number(avg_dpr)}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"☠️ **Total Kills:** {format_number(total_kills)}\n"
                f"💀 **Total Muertes:** {format_number(total_deaths)}\n"
                f"🏆 **Total Score:** {format_number(total_score)}\n"
                f"🎮 **Total Rondas:** {format_number(total_rounds)}"
            ),
            inline=False,
        )

        # K/D chart for the suggested team
        team_chart_items = [(j["Player"], j["K/D Ratio"], "#00FFFF") for j in equipo]
        team_buf = render_horizontal_bars(team_chart_items, title=f"K/D Equipo Sugerido", max_value=3.0)
        team_file = discord.File(team_buf, filename="team_kd.png")
        embed.set_image(url="attachment://team_kd.png")

        next_offset = offset + num_jugadores
        # Only show the button if there are more players to suggest
        if next_offset < len(jugadores_ordenados):
            view = OtraSugerenciaView(self, ctx, clan, num_jugadores, next_offset)
            await ctx.send(embed=embed, file=team_file, view=view)
        else:
            embed.set_footer(text="No hay mas jugadores disponibles para otra sugerencia.")
            await ctx.send(embed=embed, file=team_file)

    @commands.hybrid_command(aliases=["suggest", "sugerir"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    @app_commands.describe(
        clan="Nombre del clan",
        num_jugadores="Cantidad de jugadores (2-8)",
    )
    @app_commands.autocomplete(clan=clan_autocomplete)
    async def sugerir_equipo(self, ctx: commands.Context, clan: str = None, num_jugadores: int = 8):
        if not clan:
            await ctx.send("Uso: `-sugerir_equipo <clan> <cantidad>`.")
            return

        if num_jugadores < 2 or num_jugadores > 8:
            await ctx.send(
                "Por favor, selecciona entre 2 y 8 jugadores. "
                "Ejemplo: `-sugerir_equipo LDH 5`."
            )
            return

        clan_tag = self.bot.clans.resolve(clan) if getattr(self.bot, "clans", None) else None
        if not clan_tag:
            await ctx.send(
                f"Clan '{clan}' no reconocido. "
                f"Los clanes validos son: {', '.join(self.bot.clans.tags)}."
            )
            return

        await self._send_sugerencia(ctx, clan_tag, num_jugadores, offset=0)

    # ── -comparar_equipos <equipo1> <equipo2> <jugadores...> ──────────────

    @commands.hybrid_command(aliases=["teamvs"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    @app_commands.describe(
        equipo1="Nombre del primer equipo",
        equipo2="Nombre del segundo equipo",
        jugadores="Jugadores separados por espacios (mitad para cada equipo)",
    )
    async def comparar_equipos(
        self,
        ctx: commands.Context,
        equipo1: str = None,
        equipo2: str = None,
        *,
        jugadores: str = None,
    ):
        if not equipo1 or not equipo2:
            await ctx.send(
                "❗ Uso: `-comparar_equipos Equipo1 Equipo2 Jugador1_E1 ... Jugador1_E2 ...`."
            )
            return

        if not jugadores:
            await ctx.send(
                "❗ Por favor, proporciona los jugadores de ambos equipos. "
                "Ejemplo: `-comparar_equipos Equipo1 Equipo2 Jugador1_E1 Jugador2_E1 ... Jugador1_E2 Jugador2_E2 ...`."
            )
            return

        nombres_jugadores = jugadores.split()

        if len(nombres_jugadores) > 16:
            await ctx.send("❗ El máximo de jugadores es 8 por equipo (16 en total).")
            return

        if len(nombres_jugadores) < 2 or len(nombres_jugadores) % 2 != 0:
            await ctx.send(
                "❗ Por favor, proporciona un número par de jugadores. "
                "Ejemplo: `-comparar_equipos Equipo1 Equipo2 Jugador1_E1 Jugador2_E1 ... Jugador1_E2 Jugador2_E2 ...`."
            )
            return

        await ctx.defer()

        try:
            data = await self.fetcher.fetch_all_players()
        except Exception as e:
            await ctx.send(ERR_DB)
            logger.error("Error: %s", e)
            return

        mitad = len(nombres_jugadores) // 2
        equipos = {
            equipo1: nombres_jugadores[:mitad],
            equipo2: nombres_jugadores[mitad:],
        }

        resultados = {}
        all_team_data = {}

        for equipo_name, nombres in equipos.items():
            equipo_data = []
            for nombre in nombres:
                found = find_player(data, nombre)
                if not found:
                    await ctx.send(f"⚠️ Jugador '{nombre}' no encontrado. Probá `-buscar <nombre>` para verificar.")
                    return
                equipo_data.append(found)

            total_score = sum(j["Total Score"] for j in equipo_data)
            total_kills = sum(j["Total Kills"] for j in equipo_data)
            total_deaths = sum(j["Total Deaths"] for j in equipo_data)
            total_rounds = sum(j["Rounds"] for j in equipo_data)
            avg_ps = sum(j["Performance Score"] for j in equipo_data) / len(equipo_data)
            avg_kpr = total_kills / total_rounds if total_rounds > 0 else 0
            avg_dpr = total_deaths / total_rounds if total_rounds > 0 else 0
            team_kd = total_kills / total_deaths if total_deaths > 0 else 0

            resultados[equipo_name] = {
                "total_score": total_score,
                "total_kills": total_kills,
                "total_deaths": total_deaths,
                "total_rounds": total_rounds,
                "avg_performance_score": avg_ps,
                "avg_kills_per_round": avg_kpr,
                "avg_deaths_per_round": avg_dpr,
                "team_kd_ratio": team_kd,
            }
            all_team_data[equipo_name] = equipo_data

        # Generate comparison chart
        team_names = list(all_team_data.keys())
        buf = render_comparison_chart(
            team_names[0],
            all_team_data[team_names[0]],
            team_names[1],
            all_team_data[team_names[1]],
        )

        embed = discord.Embed(
            title=f"📊 {equipo1} vs {equipo2}",
            description=f"Comparación de equipos personalizados ({mitad} jugadores c/u)",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=BOT_THUMBNAIL)

        for equipo_name, datos in resultados.items():
            roster = ", ".join(p["Player"] for p in all_team_data[equipo_name])
            embed.add_field(
                name=f"⚔️ {equipo_name}",
                value=(
                    f"👥 {roster}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💥 **K/D Equipo:** {format_number(datos['team_kd_ratio'])}\n"
                    f"🌟 **Avg Performance:** {format_number(datos['avg_performance_score'])}\n"
                    f"🔫 **Kills/Ronda:** {format_number(datos['avg_kills_per_round'])}\n"
                    f"💀 **Muertes/Ronda:** {format_number(datos['avg_deaths_per_round'])}\n"
                    f"☠️ **Total Kills:** {format_number(datos['total_kills'])}\n"
                    f"🏆 **Total Score:** {format_number(datos['total_score'])}\n"
                    f"🎮 **Rondas:** {format_number(datos['total_rounds'])}"
                ),
                inline=True,
            )

        # Team-level comparison bars chart
        t_names = list(resultados.keys())
        comparison_metrics = [
            ("K/D", resultados[t_names[0]]["team_kd_ratio"], resultados[t_names[1]]["team_kd_ratio"]),
            ("Avg PS", resultados[t_names[0]]["avg_performance_score"], resultados[t_names[1]]["avg_performance_score"]),
            ("Kills/Ronda", resultados[t_names[0]]["avg_kills_per_round"], resultados[t_names[1]]["avg_kills_per_round"]),
            ("Muertes/Ronda", resultados[t_names[0]]["avg_deaths_per_round"], resultados[t_names[1]]["avg_deaths_per_round"]),
        ]
        comp_buf = render_comparison_bars(
            comparison_metrics,
            name1=t_names[0],
            name2=t_names[1],
            title=f"{t_names[0]} vs {t_names[1]}",
        )
        comp_file = discord.File(comp_buf, filename="team_comparison_bars.png")
        embed.set_image(url="attachment://team_comparison_bars.png")
        embed.set_footer(text=standard_footer(data))
        await ctx.send(embed=embed, file=comp_file)

        # Per-player K/D chart as follow-up
        kd_file = discord.File(buf, filename="team_comparison.png")
        kd_embed = discord.Embed(
            title=f"📊 K/D por Jugador: {equipo1} vs {equipo2}",
            color=discord.Color.blue(),
        )
        kd_embed.set_image(url="attachment://team_comparison.png")
        await ctx.send(embed=kd_embed, file=kd_file)


    # ── -prediccion <jugadores_equipo1> vs <jugadores_equipo2> ──────────

    @commands.hybrid_command(aliases=["predict", "pred"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    @app_commands.describe(
        jugadores="Jugadores: Equipo1_J1 Equipo1_J2 ... vs Equipo2_J1 Equipo2_J2 ..."
    )
    async def prediccion(self, ctx: commands.Context, *, jugadores: str = None):
        """Predice el ganador entre dos equipos basándose en estadísticas."""
        if not jugadores or " vs " not in jugadores:
            await ctx.send(
                "❗ Uso: `-prediccion Jugador1 Jugador2 Jugador3 vs Jugador4 Jugador5 Jugador6`."
            )
            return

        parts = jugadores.split(" vs ", 1)
        team1_names = parts[0].strip().split()
        team2_names = parts[1].strip().split()

        if not team1_names or not team2_names:
            await ctx.send("❗ Ambos equipos deben tener al menos un jugador.")
            return

        if len(team1_names) > 8 or len(team2_names) > 8:
            await ctx.send("❗ El máximo de jugadores por equipo es 8.")
            return

        try:
            data = await self.fetcher.fetch_all_players()
        except Exception as e:
            await ctx.send(ERR_DB)
            logger.error("Error: %s", e)
            return

        # Try to load dynamic predictor weights
        tier_config = None
        try:
            tier_config = await self.fetcher.fetch_tier_config()
        except Exception:
            pass

        def find_players(names):
            players = []
            for name in names:
                found = find_player(data, name)
                if not found:
                    return None, name
                players.append(found)
            return players, None

        team1, missing1 = find_players(team1_names)
        if team1 is None:
            await ctx.send(f"⚠️ Jugador '{missing1}' no encontrado. Probá `-buscar <nombre>` para verificar.")
            return

        team2, missing2 = find_players(team2_names)
        if team2 is None:
            await ctx.send(f"⚠️ Jugador '{missing2}' no encontrado. Probá `-buscar <nombre>` para verificar.")
            return

        # Fetch demo data for winrate bonus (if available)
        demo_data = None
        try:
            demo_data = await self.fetcher.fetch_player_details()
        except Exception:
            pass

        def _get_demo_winrate(player_name: str) -> float:
            """Get player's demo winrate (0.0-1.0), or 0.5 if not found."""
            if not demo_data:
                return 0.5
            dp = find_player(demo_data, player_name, key="ign")
            if dp:
                w = dp.get("wins", 0)
                l = dp.get("losses", 0)
                total = w + l
                return w / total if total > 3 else 0.5  # min 3 games for reliability
            return 0.5

        def team_stats(players):
            avg_ps = sum(p.get("Performance Score", 0) for p in players) / len(players)
            avg_kd = sum(p.get("K/D Ratio", 0) for p in players) / len(players)
            avg_kpr = sum(p.get("Kills per Round", 0) for p in players) / len(players)
            avg_wr = sum(_get_demo_winrate(p["Player"]) for p in players) / len(players)
            return avg_ps, avg_kd, avg_kpr, avg_wr

        t1_ps, t1_kd, t1_kpr, t1_wr = team_stats(team1)
        t2_ps, t2_kd, t2_kpr, t2_wr = team_stats(team2)

        # Dynamic weights from tier_config.json
        pw = (tier_config or {}).get("predictor_weights", {"ps": 0.40, "kd": 0.25, "kpr": 0.15, "winrate": 0.20})
        def weighted_score(ps, kd, kpr, wr):
            return ps * pw["ps"] + kd * pw["kd"] + kpr * pw["kpr"] + wr * pw["winrate"]

        t1_weighted = weighted_score(t1_ps, t1_kd, t1_kpr, t1_wr)
        t2_weighted = weighted_score(t2_ps, t2_kd, t2_kpr, t2_wr)

        total = t1_weighted + t2_weighted
        if total > 0:
            t1_prob = (t1_weighted / total) * 100
            t2_prob = (t2_weighted / total) * 100
        else:
            t1_prob = 50.0
            t2_prob = 50.0

        team1_label = " ".join(team1_names)
        team2_label = " ".join(team2_names)

        if t1_prob > t2_prob:
            winner = f"🏆 **Equipo 1** ({team1_label}) tiene ventaja."
            color = discord.Color.green()
        elif t2_prob > t1_prob:
            winner = f"🏆 **Equipo 2** ({team2_label}) tiene ventaja."
            color = discord.Color.red()
        else:
            winner = "🤝 Ambos equipos están igualados."
            color = discord.Color.gold()

        # Visual probability chart
        prob_buf = render_probability_bar(
            t1_prob / 100, t2_prob / 100,
            label_a="Equipo 1", label_b="Equipo 2"
        )
        prob_file = discord.File(prob_buf, filename="prediccion.png")

        embed = discord.Embed(
            title="🔮 Predicción de Partido",
            description=winner,
            color=color,
        )
        embed.set_image(url="attachment://prediccion.png")
        embed.set_thumbnail(url=BOT_THUMBNAIL)

        embed.add_field(
            name=f"📊 Equipo 1",
            value=(
                f"👥 {', '.join(team1_names)}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🌟 **Avg Performance:** {format_number(t1_ps)}\n"
                f"💥 **Avg K/D:** {format_number(t1_kd)}\n"
                f"🔫 **Avg Kills/Ronda:** {format_number(t1_kpr)}"
            ),
            inline=True,
        )

        embed.add_field(
            name=f"📊 Equipo 2",
            value=(
                f"👥 {', '.join(team2_names)}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🌟 **Avg Performance:** {format_number(t2_ps)}\n"
                f"💥 **Avg K/D:** {format_number(t2_kd)}\n"
                f"🔫 **Avg Kills/Ronda:** {format_number(t2_kpr)}"
            ),
            inline=True,
        )

        # Check for low-sample players in either team
        low_sample_players = []
        for p in team1:
            if p.get("Rounds", 0) < 50:
                low_sample_players.append(p["Player"])
        for p in team2:
            if p.get("Rounds", 0) < 50:
                low_sample_players.append(p["Player"])

        if low_sample_players:
            embed.add_field(
                name="⚠️ Advertencia de muestra",
                value=(
                    f"Los siguientes jugadores tienen < 50 rondas: "
                    f"**{', '.join(low_sample_players)}**\n"
                    "La predicción puede ser menos confiable."
                ),
                inline=False,
            )

        embed.set_footer(
            text=f"📐 Pesos: {int(pw['ps']*100)}% PS · {int(pw['kd']*100)}% K/D · {int(pw['kpr']*100)}% KPR · {int(pw['winrate']*100)}% WR"
        )
        await ctx.send(embed=embed, file=prob_file)


    # ── -compare_tops <clan1> <clan2> <N> ──────────────────────────────

    @commands.hybrid_command(aliases=["tops", "topvs"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    @app_commands.describe(
        clan1="Primer clan",
        clan2="Segundo clan",
        cantidad="Cantidad de tops a comparar (default: 5)",
    )
    @app_commands.autocomplete(clan1=clan_autocomplete, clan2=clan_autocomplete)
    async def compare_tops(
        self,
        ctx: commands.Context,
        clan1: str = None,
        clan2: str = None,
        cantidad: str = "5",
    ):
        """Compara los top X jugadores de dos clanes."""
        if not clan1 or not clan2:
            await ctx.send(
                "❗ Uso: `-compare_tops <clan1> <clan2> [cantidad]`.\n"
                "Ejemplo: `-compare_tops LDH SAE 5`"
            )
            return

        # Parse cantidad — may arrive as string from prefix commands
        try:
            n = int(cantidad)
        except (ValueError, TypeError):
            await ctx.send("❗ La cantidad debe ser un número. Ejemplo: `-compare_tops LDH SAE 10`")
            return

        if n < 1 or n > 15:
            await ctx.send("❗ La cantidad debe ser entre 1 y 15.")
            return
        cantidad_int = n

        try:
            data = await self.fetcher.fetch_all_players()
        except Exception as e:
            await ctx.send(ERR_DB)
            logger.error("Error: %s", e)
            return

        # Resolve clan names (case-insensitive)
        all_clan_names = {p.get("Clan", "") for p in data if p.get("Clan")}
        c1 = next((c for c in all_clan_names if c.upper() == clan1.upper()), None)
        c2 = next((c for c in all_clan_names if c.upper() == clan2.upper()), None)

        if not c1:
            await ctx.send(f"⚠️ Clan '{clan1}' no encontrado.")
            return
        if not c2:
            await ctx.send(f"⚠️ Clan '{clan2}' no encontrado.")
            return

        # Get top N players per clan by Performance Score
        def top_players(clan_name, n):
            players = [p for p in data if p.get("Clan", "") == clan_name]
            return sorted(players, key=lambda p: p.get("Performance Score", 0), reverse=True)[:n]

        top1 = top_players(c1, cantidad_int)
        top2 = top_players(c2, cantidad_int)

        if not top1:
            await ctx.send(f"⚠️ No hay jugadores en el clan '{c1}'.")
            return
        if not top2:
            await ctx.send(f"⚠️ No hay jugadores en el clan '{c2}'.")
            return

        # Aggregate stats for each top-N group
        def aggregate(players):
            n = len(players)
            total_kills = sum(p.get("Total Kills", 0) for p in players)
            total_deaths = sum(p.get("Total Deaths", 0) for p in players)
            total_score = sum(p.get("Total Score", 0) for p in players)
            total_rounds = sum(p.get("Rounds", 0) for p in players)
            avg_ps = sum(p.get("Performance Score", 0) for p in players) / n
            avg_kd = sum(p.get("K/D Ratio", 0) for p in players) / n
            avg_kpr = sum(p.get("Kills per Round", 0) for p in players) / n
            avg_spr = sum(p.get("Score per Round", 0) for p in players) / n
            team_kd = total_kills / total_deaths if total_deaths > 0 else 0
            return {
                "kills": total_kills, "deaths": total_deaths,
                "score": total_score, "rounds": total_rounds,
                "count": n, "avg_ps": avg_ps, "avg_kd": avg_kd,
                "avg_kpr": avg_kpr, "avg_spr": avg_spr, "team_kd": team_kd,
            }

        s1 = aggregate(top1)
        s2 = aggregate(top2)

        # Compare metrics — misma tabla alineada que -compare
        metrics = [
            ("Avg Perf.", s1["avg_ps"], s2["avg_ps"], True),
            ("Avg K/D", s1["avg_kd"], s2["avg_kd"], True),
            ("Avg Kills/R", s1["avg_kpr"], s2["avg_kpr"], True),
            ("Avg Score/R", s1["avg_spr"], s2["avg_spr"], True),
            ("K/D Equipo", s1["team_kd"], s2["team_kd"], True),
            ("Total Kills", s1["kills"], s2["kills"], True),
            ("Total Score", s1["score"], s2["score"], True),
        ]
        table, c1_wins, c2_wins, ties = versus_table(c1, c2, metrics)

        if c1_wins > c2_wins:
            winner = c1
        elif c2_wins > c1_wins:
            winner = c2
        else:
            winner = None

        summary = (
            f"**Resultado:** {winner} gana {max(c1_wins, c2_wins)}/{len(metrics)} categorías"
            if winner
            else f"**Resultado:** Empate {c1_wins}/{len(metrics)} categorías cada uno"
        )

        # Build roster strings
        roster1 = ", ".join(p["Player"] for p in top1)
        roster2 = ", ".join(p["Player"] for p in top2)

        embed = discord.Embed(
            title=f"🏆 Top {cantidad_int}: {c1} vs {c2}",
            description=(
                f"Comparando los **top {cantidad_int}** jugadores de cada clan\n"
                f"(por Performance Score)\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.gold(),
        )

        embed.add_field(
            name=f"👥 {c1} ({s1['count']} jugadores)",
            value=roster1,
            inline=True,
        )
        embed.add_field(
            name=f"👥 {c2} ({s2['count']} jugadores)",
            value=roster2,
            inline=True,
        )
        embed.add_field(name="\u200b", value="\u200b", inline=False)  # spacer
        embed.add_field(
            name="📊 Comparación (▲ = mejor)",
            value=table,
            inline=False,
        )
        embed.add_field(
            name="🏆 Veredicto",
            value=summary,
            inline=False,
        )

        # Build multi-comparison chart (function normalizes internally)
        chart_labels = ["Avg PS", "Avg K/D", "Avg KPR", "Avg SPR", "K/D Equipo", "Total Kills", "Total Score"]
        vals1 = [s1["avg_ps"], s1["avg_kd"], s1["avg_kpr"], s1["avg_spr"], s1["team_kd"], s1["kills"], s1["score"]]
        vals2 = [s2["avg_ps"], s2["avg_kd"], s2["avg_kpr"], s2["avg_spr"], s2["team_kd"], s2["kills"], s2["score"]]
        chart_buf = render_multi_comparison(c1, vals1, c2, vals2, chart_labels, f"Top {cantidad_int}: {c1} vs {c2}")
        file = discord.File(chart_buf, filename="compare_tops.png")
        embed.set_image(url="attachment://compare_tops.png")

        embed.set_footer(text=standard_footer(data))
        view = InvertCompareView(self, ctx, clan1, clan2)
        await ctx.send(embed=embed, file=file, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Compare(bot))
