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
from bot.services.team_model import (
    Model, resolve_names, split_teams, roles_text, prob_band,
    BAND_HELP, FEW_ROUNDS, MIN_ROUNDS,
)

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
            ]
            # Totales y actividad: los gana quien más jugó, no quien juega mejor. Se
            # muestran aparte y no cuentan para el veredicto.
            volume_metrics = [
                ("Rondas", p1.get("Rounds", 0), p2.get("Rounds", 0), True),
                ("Total Kills", p1.get("Total Kills", 0), p2.get("Total Kills", 0), True),
                ("Total Score", p1.get("Total Score", 0), p2.get("Total Score", 0), True),
                ("Participación", p1.get("Activity Index", 0), p2.get("Activity Index", 0), True),
            ]
            table, p1_wins, p2_wins, _ties = versus_table(entity1, entity2, metrics)

            # Bloque extra de demos: SOLO jugador-vs-jugador y SOLO si ambos tienen
            # >=5 rondas de demos (cobertura parcial: ~1 de cada 3 jugadores). No
            # cuenta para el veredicto, así el resultado no depende de si hay demos.
            demo_table = demo_note = demo_metrics = None
            try:
                demo_data = await self.fetcher.fetch_player_details()
            except Exception:
                demo_data = None
            if isinstance(demo_data, list):
                # Match EXACTO (case-insensitive) contra el nombre canónico de prstats:
                # el fallback parcial de find_player servía para resolver a quién te
                # referís, pero acá ATRIBUYE stats — "W4RR10R" matcheaba por substring
                # la entrada de "BSK.W4RR10R" y el bloque mostraba la misma data dos
                # veces (todo empates). Los ign de player_details son nombres prstats.
                def _demo_exact(name):
                    nl = (name or "").lower()
                    return next((e for e in demo_data if e.get("ign", "").lower() == nl), None)

                d1 = _demo_exact(p1.get("Player"))
                d2 = _demo_exact(p2.get("Player"))
                if (
                    d1 and d2 and d1 is not d2
                    and d1.get("rounds_played", 0) >= 5 and d2.get("rounds_played", 0) >= 5
                ):
                    def _rate(d, key):
                        return d.get(key, 0) / max(d.get("rounds_played", 1), 1)

                    def _wr(d):
                        decided = d.get("wins", 0) + d.get("losses", 0)
                        return d.get("wins", 0) / decided * 100 if decided else 0.0

                    def _decided(d):
                        return d.get("wins", 0) + d.get("losses", 0)

                    # Winrate + teamwork + consistencia: los componentes de demo que pesan
                    # en el Performance Score y no se ven en las stats de prstats. El
                    # winrate se muestra con el nº de partidas decididas al lado, porque el
                    # PS lo ajusta por muestra (una racha corta pesa menos).
                    demo_metrics = [
                        ("Winrate %", _wr(d1), _wr(d2), True),
                        ("Part. (WR)", _decided(d1), _decided(d2), True),
                        ("Teamwork %", max(d1.get("teamwork_ratio", 0), 0) * 100, max(d2.get("teamwork_ratio", 0), 0) * 100, True),
                        ("Consistencia", d1.get("consistency_score", 0), d2.get("consistency_score", 0), True),
                        ("Revives/R", _rate(d1, "total_revives_given"), _rate(d2, "total_revives_given"), True),
                        ("Banderas/R", _rate(d1, "total_flags_captured"), _rate(d2, "total_flags_captured"), True),
                        ("Mejor racha", d1.get("best_killstreak", 0), d2.get("best_killstreak", 0), True),
                    ]
                    demo_table, dw1, dw2, _ = versus_table(entity1, entity2, demo_metrics)
                    demo_note = (
                        f"Rondas con demo: {d1['rounds_played']} vs {d2['rounds_played']} · no cuenta "
                        f"para el veredicto; el winrate se ajusta por nº de partidas en el Performance Score."
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
                metrics=metrics, warning=warning,
                footer="Datos actualizados " + standard_footer(p1).replace("📅 ", ""), demo_for=demo_for,
                radar_filename="radar_vs.png" if radar_file else None,
                demo_metrics=demo_metrics if demo_table else None, demo_note=demo_note,
                volume_metrics=volume_metrics,
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

            # El veredicto usa solo lo que no depende del tamaño del clan.
            clan_metrics = [
                ("K/D del clan", s1["team_kd"], s2["team_kd"], True),
                ("K/D promedio", s1["avg_kd"], s2["avg_kd"], True),
                ("Perf. prom.", s1["avg_ps"], s2["avg_ps"], True),
                ("Kills/ronda", s1["kills"] / max(s1["rounds"], 1), s2["kills"] / max(s2["rounds"], 1), True),
            ]
            size_metrics = [
                ("Miembros", s1["members"], s2["members"], True),
                ("Total Kills", s1["kills"], s2["kills"], True),
                ("Total Rondas", s1["rounds"], s2["rounds"], True),
                ("Actividad", s1["avg_act"], s2["avg_act"], True),
            ]
            table, e1_wins, e2_wins, ties = versus_table(entity1, entity2, clan_metrics)
            size_table, _, _, _ = versus_table(entity1, entity2, size_metrics)

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
            embed.add_field(name="👥 Tamaño y actividad (no cuenta para el veredicto)",
                            value=size_table, inline=False)

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

        r = await self._resolve_or_report(ctx, data, nombres_jugadores)
        if not r:
            return
        equipo, partial, dups = r
        try:
            tc = await self.fetcher.fetch_tier_config()
        except Exception:
            tc = None
        try:
            demo = await self.fetcher.fetch_player_details()
        except Exception:
            demo = None
        model = Model(data, tc)

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

        embed.add_field(name="🧭 Fuerza y roles", value=self._team_field(model, equipo, demo), inline=False)
        warn = self._warnings([equipo], partial, dups)
        if warn:
            embed.add_field(name="ℹ️ A tener en cuenta", value=warn[:1024], inline=False)

        file = discord.File(buf, filename="team_analysis.png")
        embed.set_image(url="attachment://team_analysis.png")
        embed.set_footer(text=standard_footer(data))
        await ctx.send(embed=embed, file=file)

    # ── -sugerir_equipo <clan> <num_jugadores> ────────────────────────────

    async def _send_sugerencia(self, ctx: commands.Context, clan: str, num_jugadores: int, offset: int = 0):
        """Sugerencia de equipo: los más fuertes del clan con el modelo de la web
        (ajustado por muestra, mínimo de rondas), de a `num_jugadores`."""
        try:
            data = await self.fetcher.fetch_json(json_url(clan))
            all_players = await self.fetcher.fetch_all_players()
        except Exception as e:
            await ctx.send(ERR_DB)
            logger.error("Error: %s", e)
            return
        try:
            tc = await self.fetcher.fetch_tier_config()
        except Exception:
            tc = None
        try:
            demo = await self.fetcher.fetch_player_details()
        except Exception:
            demo = None
        model = Model(all_players, tc)
        pool = [p for p in (data or []) if (p.get("Rounds") or 0) >= MIN_ROUNDS]
        ordenados = sorted(pool, key=model.strength, reverse=True)
        if offset >= len(ordenados):
            offset = 0
        equipo = ordenados[offset: offset + num_jugadores]
        if not equipo:
            await ctx.send(f"**{clan}** no tiene jugadores con {MIN_ROUNDS}+ rondas para sugerir.")
            return

        n = (offset // num_jugadores) + 1
        embed = discord.Embed(
            title=f"🎯 Equipo sugerido para {clan} (#{n})",
            description=(f"Los **{len(equipo)}** más fuertes del clan con {MIN_ROUNDS}+ rondas "
                         f"({len(pool)} disponibles), por fuerza: Performance, K/D y kills por ronda "
                         "ajustados por muestra, como en la web."),
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=BOT_THUMBNAIL)
        rows = []
        for i, p in enumerate(equipo, offset + 1):
            rows.append(f"`{i:>2}.` **{p['Player']}**: fuerza {model.strength(p) * 100:.0f} · "
                        f"Perf. {p.get('Performance Score', 0):.3f} · K/D {p.get('K/D Ratio', 0):.2f} · "
                        f"{format_number(p.get('Rounds', 0))} rondas")
        embed.add_field(name="👥 Jugadores", value="\n".join(rows)[:1024], inline=False)
        embed.add_field(name="📊 El equipo", value=self._team_field(model, equipo, demo), inline=False)

        chart = [(p["Player"], model.strength(p) * 100, "#00FFFF") for p in equipo]
        buf = render_horizontal_bars(chart, title="Fuerza (de 100)", max_value=100)
        file = discord.File(buf, filename="team_kd.png")
        embed.set_image(url="attachment://team_kd.png")

        next_offset = offset + num_jugadores
        if next_offset < len(ordenados):
            embed.set_footer(text="«Otra sugerencia» muestra los siguientes por fuerza.")
            view = OtraSugerenciaView(self, ctx, clan, num_jugadores, next_offset)
            await ctx.send(embed=embed, file=file, view=view)
        else:
            embed.set_footer(text="No hay más jugadores con suficientes rondas para otra sugerencia.")
            await ctx.send(embed=embed, file=file)

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

    # ── Equipos: helpers del modelo (el mismo de la web) ─────────────────

    async def _team_ctx(self, ctx):
        """(jugadores, modelo, demos) o None si falló la carga."""
        try:
            data = await self.fetcher.fetch_all_players()
        except Exception as e:
            await ctx.send(ERR_DB)
            logger.error("Error: %s", e)
            return None
        try:
            tc = await self.fetcher.fetch_tier_config()
        except Exception:
            tc = None
        try:
            demo = await self.fetcher.fetch_player_details()
        except Exception:
            demo = None
        return data, Model(data, tc), demo

    async def _resolve_or_report(self, ctx, data, names):
        found, missing, partial, dups = resolve_names(data, names)
        if missing:
            await ctx.send(
                "⚠️ No encontré a: " + ", ".join(f"**{m}**" for m in missing)
                + ". Probá `-buscar <nombre>` para ver cómo está escrito."
            )
            return None
        return found, partial, dups

    @staticmethod
    def _team_field(model, team, demo):
        score = model.team_score(team)

        def avg(k):
            return sum((p.get(k) or 0) for p in team) / len(team)

        lines = [
            "👥 " + ", ".join(p["Player"] for p in team),
            f"**Fuerza:** {score * 100:.0f} de 100",
            f"Performance {avg('Performance Score'):.3f} · K/D {avg('K/D Ratio'):.2f} · "
            f"Kills/ronda {avg('Kills per Round'):.2f}",
        ]
        rt = roles_text(team, demo)
        if rt:
            lines.append(rt)
        return "\n".join(lines)[:1024]

    @staticmethod
    def _warnings(teams, partial, dups):
        out = []
        if partial:
            out.append("🔎 Nombres resueltos: " + ", ".join(f"{a} → **{b}**" for a, b in partial))
        if dups:
            out.append("♻️ Repetidos (se cuentan una vez): " + ", ".join(dups))
        few = [p["Player"] for t in teams for p in t if (p.get("Rounds") or 0) < FEW_ROUNDS]
        if few:
            out.append(f"🟡 Con menos de {FEW_ROUNDS} rondas cuentan cerca del promedio: " + ", ".join(few))
        return "\n".join(out)

    async def _send_matchup(self, ctx, model, demo, name1, team1, name2, team2, partial, dups):
        prob = model.win_prob(team1, team2, by_size=True)
        fav, fav_p = (name1, prob) if prob >= 0.5 else (name2, 1 - prob)
        band = prob_band(prob)
        if band == "parejo":
            desc = f"🤝 **Parejo:** {name1} {prob:.0%} · {name2} {1 - prob:.0%}"
            color = discord.Color.gold()
        else:
            desc = f"🏆 **{fav}** tiene **{fav_p:.0%}** de ganar: {band}"
            color = discord.Color.green() if fav == name1 else discord.Color.red()
        if len(team1) != len(team2):
            desc += (f"\n-# {len(team1)} contra {len(team2)}: el equipo más chico suma menos "
                     "(los lugares vacíos valen cero).")
        embed = discord.Embed(title=f"🔮 {name1} vs {name2}", description=desc, color=color)
        embed.add_field(name=f"⚔️ {name1}", value=self._team_field(model, team1, demo), inline=True)
        embed.add_field(name=f"⚔️ {name2}", value=self._team_field(model, team2, demo), inline=True)
        warn = self._warnings([team1, team2], partial, dups)
        if warn:
            embed.add_field(name="ℹ️ A tener en cuenta", value=warn[:1024], inline=False)
        buf = render_probability_bar(prob, 1 - prob, label_a=name1[:20], label_b=name2[:20])
        file = discord.File(buf, filename="prediccion.png")
        embed.set_image(url="attachment://prediccion.png")
        embed.set_footer(text=f"Cómo leerlo: {BAND_HELP}. No ve mapa, modo ni comunicación.")
        await ctx.send(embed=embed, file=file)

    # ── -prediccion <jugadores> vs <jugadores> ───────────────────────────

    @commands.hybrid_command(aliases=["predict", "pred"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    @app_commands.describe(jugadores="Equipo 1 vs Equipo 2, p. ej.: juan pedro vs ana luis")
    async def prediccion(self, ctx: commands.Context, *, jugadores: str = None):
        """Probabilidad de ganar entre dos equipos (mismo modelo que la web)."""
        teams = split_teams(jugadores or "")
        if not teams or not teams[0] or not teams[1]:
            await ctx.send(
                "❗ Separá los equipos con `vs`: `-prediccion juan pedro vs ana luis`.\n"
                "-# También sirve `contra` o `|`. Para repartir una lista en dos equipos parejos: `-balancear`."
            )
            return
        if len(teams[0]) > 8 or len(teams[1]) > 8:
            await ctx.send("❗ Hasta 8 jugadores por equipo.")
            return
        await ctx.defer()
        loaded = await self._team_ctx(ctx)
        if not loaded:
            return
        data, model, demo = loaded
        r1 = await self._resolve_or_report(ctx, data, teams[0])
        if not r1:
            return
        r2 = await self._resolve_or_report(ctx, data, teams[1])
        if not r2:
            return
        names1 = {p["Player"] for p in r1[0]}
        both = [p["Player"] for p in r2[0] if p["Player"] in names1]
        if both:
            await ctx.send("❗ Un jugador no puede estar en los dos equipos: " + ", ".join(f"**{n}**" for n in both))
            return
        await self._send_matchup(ctx, model, demo, "Equipo 1", r1[0], "Equipo 2", r2[0],
                                 r1[1] + r2[1], r1[2] + r2[2])

    # ── -comparar_equipos <nombre1> <nombre2> <jugadores> ────────────────

    @commands.hybrid_command(aliases=["teamvs"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    @app_commands.describe(
        equipo1="Nombre del primer equipo",
        equipo2="Nombre del segundo equipo",
        jugadores="Jugadores del equipo 1 vs jugadores del equipo 2",
    )
    async def comparar_equipos(self, ctx: commands.Context, equipo1: str = None,
                               equipo2: str = None, *, jugadores: str = None):
        uso = ("❗ Uso: `-comparar_equipos Rojos Azules juan pedro vs ana luis`\n"
               "-# Primero los dos nombres de equipo, después los jugadores separados con `vs`. "
               "Sin `vs`, la primera mitad va al primer equipo.")
        if not equipo1 or not equipo2 or not jugadores:
            await ctx.send(uso)
            return
        teams = split_teams(jugadores)
        if not teams:
            names = jugadores.split()
            if len(names) < 2 or len(names) % 2:
                await ctx.send(uso)
                return
            teams = (names[: len(names) // 2], names[len(names) // 2:])
        if not teams[0] or not teams[1] or len(teams[0]) > 8 or len(teams[1]) > 8:
            await ctx.send("❗ Cada equipo necesita entre 1 y 8 jugadores.\n" + uso)
            return
        await ctx.defer()
        loaded = await self._team_ctx(ctx)
        if not loaded:
            return
        data, model, demo = loaded
        r1 = await self._resolve_or_report(ctx, data, teams[0])
        if not r1:
            return
        r2 = await self._resolve_or_report(ctx, data, teams[1])
        if not r2:
            return
        await self._send_matchup(ctx, model, demo, equipo1, r1[0], equipo2, r2[0],
                                 r1[1] + r2[1], r1[2] + r2[2])

    # ── -balancear <jugadores> ───────────────────────────────────────────

    @commands.hybrid_command(aliases=["balance", "repartir"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    @app_commands.describe(jugadores="Entre 2 y 16 jugadores separados por espacios")
    async def balancear(self, ctx: commands.Context, *, jugadores: str = None):
        """Reparte una lista de jugadores en dos equipos lo más parejos posible."""
        names = (jugadores or "").replace(",", " ").split()
        if len(names) < 2 or len(names) > 16:
            await ctx.send("❗ Pasame entre 2 y 16 jugadores: `-balancear juan pedro ana luis`.")
            return
        await ctx.defer()
        loaded = await self._team_ctx(ctx)
        if not loaded:
            return
        data, model, demo = loaded
        r = await self._resolve_or_report(ctx, data, names)
        if not r:
            return
        players, partial, dups = r
        if len(players) < 2:
            await ctx.send("❗ Quedan menos de 2 jugadores distintos.")
            return
        a, b = model.balance(players)
        await self._send_matchup(ctx, model, demo, "Equipo A", a, "Equipo B", b, partial, dups)


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
