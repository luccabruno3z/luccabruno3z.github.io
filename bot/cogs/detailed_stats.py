"""DetailedStats cog -- commands powered by .PRdemo data (kits, vehicles, revives, maps)."""

import logging
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

from bot.assets.kit_mapping import (
    get_kit_display, get_kit_emoji, classify_kit, normalize_kits, clean_weapon_name,
    clean_map_name, clean_vehicle_name, weapon_model_name, is_personal_weapon,
    clean_gamemode, weapon_vehicle_name, weapon_vclass, is_vehicle_kill,
    weapon_vtype, weapon_category, clean_seat,
)
from bot.assets.vehicle_mapping import get_vehicle_emoji, get_vehicle_emoji_by_name
from bot.config import BOT_THUMBNAIL, performance_color
from bot.services.chart_renderer import render_bar_chart, render_horizontal_bars, render_multi_comparison
from bot.ui.leaderboard_card import LeaderboardView
from bot.utils import format_number, find_player, standard_footer, progress_bar
from bot.views.explain import ExplainView

logger = logging.getLogger(__name__)


# ── Autocomplete helpers ─────────────────────────────────────────────────────

async def demo_player_autocomplete(
    interaction: discord.Interaction, current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete for player names from demo data."""
    try:
        data = await interaction.client.data_fetcher.fetch_player_details()
    except Exception:
        return []
    names = [p["ign"] for p in data]
    filtered = [n for n in names if current.lower() in n.lower()][:25]
    return [app_commands.Choice(name=n, value=n) for n in filtered]


async def map_name_autocomplete(
    interaction: discord.Interaction, current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete for map names from demo data."""
    try:
        data = await interaction.client.data_fetcher.fetch_map_stats()
    except Exception:
        return []
    names = sorted({m["map_name"] for m in data})
    filtered = [n for n in names if current.lower() in n.lower()][:25]
    return [app_commands.Choice(name=n, value=n) for n in filtered]


def _find_demo_player(data: list[dict], name: str) -> Optional[dict]:
    """Find a player in demo data (keyed by 'ign'). Misma cascada que el resto de
    comandos (exacta case-sensitive → case-insensitive → parcial)."""
    return find_player(data, name, key="ign")


def _top_items(d: dict, n: int = 5) -> list[tuple[str, int]]:
    """Return top N items from a dict sorted by value descending."""
    return sorted(d.items(), key=lambda x: x[1], reverse=True)[:n]


def _top_named(d: dict, namer, n: int = 10, exclude=None) -> list[tuple[str, int]]:
    """Agrupa codes crudos por su nombre legible (colapsa variantes/facciones) y
    devuelve el top N ya nombrado. Evita listas/gráficos saturados de variantes.
    `exclude(code)` descarta codes (p.ej. entorno '?' o armas de vehículo)."""
    agg: dict[str, int] = {}
    for code, cnt in (d or {}).items():
        if exclude and exclude(code):
            continue
        name = namer(code)
        agg[name] = agg.get(name, 0) + cnt
    return sorted(agg.items(), key=lambda x: x[1], reverse=True)[:n]


class DetailedStats(commands.Cog):
    """Comandos de estadísticas detalladas basados en datos de demos (.PRdemo)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def fetcher(self):
        return self.bot.data_fetcher

    # ── -kits <jugador> ──────────────────────────────────────────────────

    def _check_mode(self, ctx: commands.Context) -> bool:
        """Return True if mode is 'prstats' (demo commands blocked)."""
        mode = self.bot.guild_settings.get_mode(ctx.guild.id) if ctx.guild else "combined"
        return mode == "prstats"

    @commands.hybrid_command(
        name="kits",
        description="Mostrar los kits más usados por un jugador (datos de demos)",
    )
    @app_commands.describe(jugador="Nombre del jugador")
    @app_commands.autocomplete(jugador=demo_player_autocomplete)
    async def kits(self, ctx: commands.Context, *, jugador: str):
        if self._check_mode(ctx):
            await ctx.send("⚠️ Estos comandos requieren modo **Demos** o **Combinado**. Usá `-ayuda` para cambiar el modo.")
            return
        data = await self.fetcher.fetch_player_details()
        player = _find_demo_player(data, jugador)

        if not player:
            await ctx.send(f"No se encontró a **{jugador}** en los datos de demos. Jugá algunas partidas más o probá `-buscar <nombre>` para verificar.")
            return

        # Normalize faction variants into base kit categories
        raw_kits = player.get("kits_used", {})
        normalized = normalize_kits(raw_kits)
        kits = _top_items(normalized, 10)
        if not kits:
            await ctx.send(f"**{player['ign']}** no tiene datos de kits registrados.")
            return

        total = sum(c for _, c in kits)
        kit_items = []
        for kit_name, count in kits:
            pct = (count / total * 100) if total > 0 else 0
            kit_items.append((kit_name, pct, "#00FFFF"))

        buf = render_horizontal_bars(kit_items, title=f"Top Kits - {player['ign']}", max_value=100, value_suffix="%")
        file = discord.File(buf, filename="kits.png")

        embed = discord.Embed(
            title=f"🎖️ Kits de {player['ign']}",
            description=f"Total de picks: **{total}**",
            color=discord.Color.blue(),
        )
        embed.set_image(url="attachment://kits.png")

        # Desempeño por kit (K/D con cada kit). Solo se calcula desde las rondas
        # nuevas (atribución de cada baja al kit puesto), así que arranca vacío y
        # se va llenando; filtramos roles con pocas kills para evitar ruido.
        perf = player.get("kit_performance", {})
        ranked = sorted(
            ((role, d.get("kills", 0), d.get("deaths", 0)) for role, d in perf.items()
             if d.get("kills", 0) >= 10),
            key=lambda x: x[1] / max(x[2], 1), reverse=True,
        )
        if ranked:
            lines = []
            for role, k, dth in ranked[:8]:
                emoji = get_kit_emoji(role) or ""
                kd = k / max(dth, 1)
                lines.append(f"{emoji} **{role}** — K/D {kd:.2f} ({k}/{dth})")
            embed.add_field(name="⚔️ Desempeño por kit", value="\n".join(lines), inline=False)
        else:
            embed.add_field(
                name="⚔️ Desempeño por kit",
                value="⏳ Acumulándose — se calcula desde las partidas nuevas (≥10 kills por kit).",
                inline=False,
            )

        embed.set_footer(text=f"Datos de {player['rounds_played']} rondas | {standard_footer()}")
        await ctx.send(embed=embed, file=file)

    # ── -vehiculos <jugador> ─────────────────────────────────────────────

    @commands.hybrid_command(
        name="vehiculos",
        description="Mostrar estadísticas de vehículos de un jugador (datos de demos)",
    )
    @app_commands.describe(jugador="Nombre del jugador")
    @app_commands.autocomplete(jugador=demo_player_autocomplete)
    async def vehiculos(self, ctx: commands.Context, *, jugador: str):
        if self._check_mode(ctx):
            await ctx.send("⚠️ Estos comandos requieren modo **Demos** o **Combinado**. Usá `-ayuda` para cambiar el modo.")
            return
        data = await self.fetcher.fetch_player_details()
        player = _find_demo_player(data, jugador)

        if not player:
            await ctx.send(f"No se encontró a **{jugador}** en los datos de demos. Jugá algunas partidas más o probá `-buscar <nombre>` para verificar.")
            return

        kw = player.get("kill_weapons", {})
        # Sección 1 — Kills CON vehículos: se arman desde kill_weapons (el arma que
        # hizo la baja), no desde vehicle_kills (que infla con kills a pie tras
        # desmontar de un transporte). Solo vehículos tripulados, agrupados por modelo.
        vehicle_kills = _top_named(kw, weapon_vehicle_name, 10,
                                   exclude=lambda c: not is_vehicle_kill(c))
        veh_total = sum(c for w, c in kw.items() if is_vehicle_kill(w))
        empl_total = sum(c for w, c in kw.items() if weapon_vclass(w) == "emplacement")
        # Sección 2 — Vehículos destruidos (anti-vehículo): conteo + desglose por tipo.
        destroyed = player.get("total_vehicles_destroyed", 0)
        destroyed_by_type = _top_named(player.get("vehicles_destroyed_by_type", {}),
                                       clean_vehicle_name, 5)
        # Sección 3 — Kills por asiento (artillero/conductor/piloto…).
        seat_kills = _top_named(player.get("seat_kills", {}), clean_seat, 6)

        if not vehicle_kills and destroyed == 0 and empl_total == 0:
            await ctx.send(f"**{player['ign']}** no tiene datos de vehículos registrados.")
            return

        embed = discord.Embed(
            title=f"🚁 Vehículos de {player['ign']}",
            color=discord.Color.dark_green(),
        )

        # 🔥 Vehículos destruidos (+ desglose por tipo si hay)
        destroyed_value = f"**{destroyed}** vehículos enemigos destruidos"
        if destroyed_by_type:
            destroyed_value += "\n" + ", ".join(
                f"{(get_vehicle_emoji_by_name(v) + ' ') if get_vehicle_emoji_by_name(v) else ''}{v} ({c})"
                for v, c in destroyed_by_type)
        embed.add_field(name="🔥 Vehículos destruidos", value=destroyed_value, inline=False)

        file = None
        if vehicle_kills:
            top_line = ", ".join(
                f"{(get_vehicle_emoji_by_name(v) + ' ') if get_vehicle_emoji_by_name(v) else ''}**{v}** ({c})"
                for v, c in vehicle_kills[:3])
            extra = f"\n🎯 Con emplazamientos/estáticos: **{empl_total}**" if empl_total else ""
            embed.add_field(
                name=f"🎯 Kills con vehículos — {veh_total}",
                value=f"Tripulando vehículos. Top: {top_line}{extra}",
                inline=False,
            )
            veh_items = [(veh, count, "#00FFFF") for veh, count in vehicle_kills]
            buf = render_horizontal_bars(veh_items, title=f"Kills con vehículos - {player['ign']}")
            file = discord.File(buf, filename="vehiculos.png")
            embed.set_image(url="attachment://vehiculos.png")
        elif empl_total:
            embed.add_field(
                name="🎯 Kills con emplazamientos",
                value=f"**{empl_total}** kills con armas emplazadas/estáticas",
                inline=False,
            )

        # 🪖 Kills por asiento (artillero/conductor/piloto…) — desde rondas nuevas.
        if seat_kills:
            embed.add_field(
                name="🪖 Kills por asiento",
                value=", ".join(f"**{s}** ({c})" for s, c in seat_kills),
                inline=False,
            )

        embed.set_footer(text=f"Datos de {player['rounds_played']} rondas | {standard_footer()}")
        if file:
            await ctx.send(embed=embed, file=file)
        else:
            embed.set_thumbnail(url=BOT_THUMBNAIL)
            await ctx.send(embed=embed)

    # ── -assets <jugador> ────────────────────────────────────────────────

    @commands.hybrid_command(
        name="assets",
        aliases=["activos", "medios"],
        description="Desglose de kills por tipo de asset: a pie, terrestres, aéreos, emplazamientos (demos)",
    )
    @app_commands.describe(jugador="Nombre del jugador")
    @app_commands.autocomplete(jugador=demo_player_autocomplete)
    async def assets(self, ctx: commands.Context, *, jugador: str):
        """Desglose de kills por tipo de asset (a pie, terrestres, aéreos, navales, emplazamientos)."""
        if self._check_mode(ctx):
            await ctx.send("⚠️ Estos comandos requieren modo **Demos** o **Combinado**. Usá `-ayuda` para cambiar el modo.")
            return
        data = await self.fetcher.fetch_player_details()
        player = _find_demo_player(data, jugador)

        if not player:
            await ctx.send(f"No se encontró a **{jugador}** en los datos de demos. Jugá algunas partidas más o probá `-buscar <nombre>` para verificar.")
            return

        kw = player.get("kill_weapons", {})
        if not kw:
            await ctx.send(f"**{player['ign']}** no tiene datos de armas registrados.")
            return

        # Categorías presentables (orden + emoji + label). 'env' = entorno/desconocido.
        CATS = [
            ("infantry", "🔫", "A pie (infantería)"),
            ("ground", "🚛", "Vehículos terrestres"),
            ("air", "✈️", "Vehículos aéreos"),
            ("naval", "🚤", "Vehículos navales"),
            ("emplacement", "🎯", "Emplazamientos / estáticos"),
            ("env", "💥", "Entorno / desconocido"),
        ]
        totals: dict[str, int] = {}
        tops: dict[str, dict[str, int]] = {}
        for w, c in kw.items():
            cat = weapon_category(w)
            totals[cat] = totals.get(cat, 0) + c
            if cat in ("ground", "air", "naval", "emplacement"):
                name = weapon_vehicle_name(w) or clean_weapon_name(w)
                d = tops.setdefault(cat, {})
                d[name] = d.get(name, 0) + c

        grand = sum(totals.values()) or 1

        embed = discord.Embed(
            title=f"🧩 Assets de {player['ign']}",
            description=f"Cómo consigue sus **{grand}** kills, por tipo de medio",
            color=discord.Color.teal(),
        )

        chart_items = []
        for cat, emoji, label in CATS:
            tot = totals.get(cat, 0)
            if tot == 0:
                continue
            pct = tot / grand * 100
            top = tops.get(cat, {})
            top_str = ""
            if top:
                top3 = sorted(top.items(), key=lambda x: x[1], reverse=True)[:3]
                top_str = "\n╰ " + ", ".join(f"{n} ({c})" for n, c in top3)
            embed.add_field(
                name=f"{emoji} {label}",
                value=f"**{tot}** kills · {pct:.0f}%{top_str}",
                inline=False,
            )
            if cat != "env":
                chart_items.append((label, pct, "#00FFFF"))

        embed.set_footer(text=f"Datos de {player['rounds_played']} rondas | {standard_footer()}")

        if chart_items:
            buf = render_horizontal_bars(chart_items, title=f"Kills por tipo de asset - {player['ign']}", max_value=100, value_suffix="%")
            file = discord.File(buf, filename="assets.png")
            embed.set_image(url="attachment://assets.png")
            await ctx.send(embed=embed, file=file)
        else:
            embed.set_thumbnail(url=BOT_THUMBNAIL)
            await ctx.send(embed=embed)

    # ── -revives <jugador> ───────────────────────────────────────────────

    @commands.hybrid_command(
        name="revives",
        description="Mostrar revives dados y recibidos por un jugador (datos de demos)",
    )
    @app_commands.describe(jugador="Nombre del jugador")
    @app_commands.autocomplete(jugador=demo_player_autocomplete)
    async def revives(self, ctx: commands.Context, *, jugador: str):
        if self._check_mode(ctx):
            await ctx.send("⚠️ Estos comandos requieren modo **Demos** o **Combinado**. Usá `-ayuda` para cambiar el modo.")
            return
        data = await self.fetcher.fetch_player_details()
        player = _find_demo_player(data, jugador)

        if not player:
            await ctx.send(f"No se encontró a **{jugador}** en los datos de demos. Jugá algunas partidas más o probá `-buscar <nombre>` para verificar.")
            return

        given = player.get("total_revives_given", 0)
        received = player.get("total_revives_received", 0)
        rounds = player.get("rounds_played", 1)

        rev_items = [
            ("Dados", given, "#00FF88"),
            ("Recibidos", received, "#FF8800"),
        ]
        buf = render_horizontal_bars(rev_items, title=f"Revives - {player['ign']}")
        file = discord.File(buf, filename="revives.png")

        embed = discord.Embed(
            title=f"💉 Revives de {player['ign']}",
            description=(
                f"Dados: **{given}** ({given/rounds:.1f}/ronda)\n"
                f"Recibidos: **{received}** ({received/rounds:.1f}/ronda)\n"
                f"Rondas analizadas: **{rounds}**"
            ),
            color=discord.Color.green(),
        )
        embed.set_image(url="attachment://revives.png")
        embed.set_footer(text=f"Datos de {rounds} rondas | {standard_footer()}")
        await ctx.send(embed=embed, file=file)

    # ── -mapa <nombre> ───────────────────────────────────────────────────

    @commands.hybrid_command(
        name="mapa",
        description="Mostrar estadísticas de un mapa (datos de demos)",
    )
    @app_commands.describe(nombre="Nombre del mapa")
    @app_commands.autocomplete(nombre=map_name_autocomplete)
    async def mapa(self, ctx: commands.Context, *, nombre: str):
        if self._check_mode(ctx):
            await ctx.send("⚠️ Estos comandos requieren modo **Demos** o **Combinado**. Usá `-ayuda` para cambiar el modo.")
            return
        data = await self.fetcher.fetch_map_stats()

        # Find map (fuzzy)
        found = None
        for m in data:
            if nombre.lower() in m["map_name"].lower():
                found = m
                break

        if not found:
            await ctx.send(f"No se encontró el mapa **{nombre}** en los datos de demos. Jugá algunas partidas más o probá `-buscar <nombre>` para verificar.")
            return

        total = found["rounds_played"]
        blufor_wr = (found["blufor_wins"] / total * 100) if total > 0 else 0
        opfor_wr = (found["opfor_wins"] / total * 100) if total > 0 else 0
        avg_kills = found["total_kills"] / total if total > 0 else 0

        map_wr_items = [
            (f"Blufor ({found['blufor_wins']}W)", blufor_wr, "#4488FF"),
            (f"Opfor ({found['opfor_wins']}W)", opfor_wr, "#FF4444"),
        ]
        buf = render_horizontal_bars(map_wr_items, title=f"Winrate - {clean_map_name(found['map_name'])}", max_value=100, value_suffix="%")
        file = discord.File(buf, filename="mapa.png")

        embed = discord.Embed(
            title=f"🗺️ {clean_map_name(found['map_name'])}",
            description=f"Gamemode: `{found['gamemode']}`",
            color=discord.Color.purple(),
        )
        embed.add_field(name="Rondas jugadas", value=f"**{total}**", inline=True)
        embed.add_field(name="Kills promedio/ronda", value=f"**{avg_kills:.0f}**", inline=True)
        embed.add_field(name="Revives totales", value=f"**{format_number(found['total_revives'])}**", inline=True)
        avg_dur = found.get("avg_duration_seconds", 0)
        if avg_dur:
            avg_dur = int(avg_dur)
            kpm = (avg_kills / (avg_dur / 60)) if avg_dur else 0
            embed.add_field(name="Duración promedio", value=f"**{avg_dur // 60}m {avg_dur % 60:02d}s**", inline=True)
            embed.add_field(name="Kills/min", value=f"**{kpm:.1f}**", inline=True)
        embed.add_field(name="Vehículos destruidos", value=f"**{format_number(found['total_vehicles_destroyed'])}**", inline=True)
        embed.add_field(
            name="Tickets promedio al final",
            value=f"Team 1: **{found['avg_tickets1_final']:.0f}** | Team 2: **{found['avg_tickets2_final']:.0f}**",
            inline=False,
        )
        embed.set_image(url="attachment://mapa.png")
        embed.set_footer(text=standard_footer())
        await ctx.send(embed=embed, file=file)

    # ── -armas <jugador> ─────────────────────────────────────────────────

    @commands.hybrid_command(
        name="armas",
        description="Mostrar las armas más usadas por un jugador (datos de demos)",
    )
    @app_commands.describe(jugador="Nombre del jugador")
    @app_commands.autocomplete(jugador=demo_player_autocomplete)
    async def armas(self, ctx: commands.Context, *, jugador: str):
        if self._check_mode(ctx):
            await ctx.send("⚠️ Estos comandos requieren modo **Demos** o **Combinado**. Usá `-ayuda` para cambiar el modo.")
            return
        data = await self.fetcher.fetch_player_details()
        player = _find_demo_player(data, jugador)

        if not player:
            await ctx.send(f"No se encontró a **{jugador}** en los datos de demos. Jugá algunas partidas más o probá `-buscar <nombre>` para verificar.")
            return

        weapons = _top_named(player.get("kill_weapons", {}), weapon_model_name, 10, exclude=lambda c: not is_personal_weapon(c))
        if not weapons:
            await ctx.send(f"**{player['ign']}** no tiene datos de armas registrados.")
            return

        total = sum(c for _, c in weapons)
        weapon_items = [(w, count, "#FF4444") for w, count in weapons]
        buf = render_horizontal_bars(weapon_items, title=f"Armas - {player['ign']}")
        file = discord.File(buf, filename="armas.png")

        embed = discord.Embed(
            title=f"🔫 Armas de {player['ign']}",
            description=f"Total de kills: **{total}**",
            color=discord.Color.red(),
        )
        embed.set_image(url="attachment://armas.png")
        embed.set_footer(text=f"Datos de {player['rounds_played']} rondas | {standard_footer()}")
        await ctx.send(embed=embed, file=file)

    # ── -perfil_demo <jugador> ───────────────────────────────────────────

    @commands.hybrid_command(
        name="perfil_demo",
        description="Perfil completo de un jugador con datos de demos",
    )
    @app_commands.describe(jugador="Nombre del jugador")
    @app_commands.autocomplete(jugador=demo_player_autocomplete)
    async def perfil_demo(self, ctx: commands.Context, *, jugador: str):
        if self._check_mode(ctx):
            await ctx.send("⚠️ Estos comandos requieren modo **Demos** o **Combinado**. Usá `-ayuda` para cambiar el modo.")
            return
        data = await self.fetcher.fetch_player_details()
        player = _find_demo_player(data, jugador)

        if not player:
            await ctx.send(f"No se encontró a **{jugador}** en los datos de demos. Jugá algunas partidas más o probá `-buscar <nombre>` para verificar.")
            return

        rounds = player.get("rounds_played", 1)
        kills = player.get("total_kills", 0)
        deaths = player.get("total_deaths", 0)
        kd = kills / deaths if deaths > 0 else kills
        score = player.get("total_score", 0)
        tw_score = player.get("total_teamwork_score", 0)
        revives_g = player.get("total_revives_given", 0)
        revives_r = player.get("total_revives_received", 0)
        vehs_destroyed = player.get("total_vehicles_destroyed", 0)
        flags = player.get("total_flags_captured", 0)

        # Top kit (normalized from faction variants)
        raw_kits = player.get("kits_used", {})
        normalized_kits = normalize_kits(raw_kits) if raw_kits else {}
        top_kits = _top_items(normalized_kits, 3)
        if top_kits:
            kit_parts = []
            for k, c in top_kits:
                emoji = get_kit_emoji(k)
                label = f"{emoji} {k}" if emoji else k
                kit_parts.append(f"{label} ({c})")
            kits_str = ", ".join(kit_parts)
        else:
            kits_str = "N/A"

        # Top weapon (agrupado por modelo)
        top_weapons = _top_named(player.get("kill_weapons", {}), weapon_model_name, 3, exclude=lambda c: not is_personal_weapon(c))
        weapons_str = ", ".join(f"**{w}** ({c})" for w, c in top_weapons) if top_weapons else "N/A"

        # Top maps (cleaned names)
        top_maps = _top_items(player.get("maps_played", {}), 3)
        maps_str = ", ".join(f"**{clean_map_name(m)}** ({c})" for m, c in top_maps) if top_maps else "N/A"

        embed = discord.Embed(
            title=f"📋 Perfil detallado: {player['ign']}",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Rondas", value=f"**{rounds}**", inline=True)
        embed.add_field(name="K/D", value=f"**{kd:.2f}** ({kills}K / {deaths}D)", inline=True)
        embed.add_field(name="Score", value=f"**{format_number(score)}** ({score/rounds:.0f}/ronda)", inline=True)
        embed.add_field(name="Teamwork", value=f"**{format_number(tw_score)}** ({tw_score/rounds:.0f}/ronda)", inline=True)
        embed.add_field(name="Revives", value=f"**{revives_g}** dados / **{revives_r}** recibidos", inline=True)
        embed.add_field(name="Vehículos destruidos", value=f"**{vehs_destroyed}**", inline=True)
        embed.add_field(name="Flags capturadas", value=f"**{flags}**", inline=True)
        embed.add_field(name="Top kits", value=kits_str, inline=False)
        embed.add_field(name="Top armas", value=weapons_str, inline=False)
        embed.add_field(name="Top mapas", value=maps_str, inline=False)
        embed.set_footer(text=standard_footer())
        embed.set_thumbnail(url=BOT_THUMBNAIL)
        await ctx.send(embed=embed)

    # ── -rol <jugador> ────────────────────────────────────────────────

    @commands.hybrid_command(
        name="rol",
        aliases=["role"],
        description="Análisis de efectividad por kit/rol de un jugador (datos de demos)",
    )
    @app_commands.describe(jugador="Nombre del jugador")
    @app_commands.autocomplete(jugador=demo_player_autocomplete)
    async def rol(self, ctx: commands.Context, *, jugador: str):
        if self._check_mode(ctx):
            await ctx.send("⚠️ Estos comandos requieren modo **Demos** o **Combinado**. Usá `-ayuda` para cambiar el modo.")
            return
        data = await self.fetcher.fetch_player_details()
        player = _find_demo_player(data, jugador)

        if not player:
            await ctx.send(f"No se encontró a **{jugador}** en los datos de demos. Jugá algunas partidas más o probá `-buscar <nombre>` para verificar.")
            return

        rounds = player.get("rounds_played", 1)
        raw_kits = player.get("kits_used", {})
        normalized = normalize_kits(raw_kits)
        total_kit_picks = sum(normalized.values()) if normalized else 0

        # Top 5 kits with % of usage
        top_kits = _top_items(normalized, 5)
        lines = []
        rol_chart_items = []
        if top_kits:
            lines.append("**Top kits por uso:**")
            for kit_name, count in top_kits:
                pct = (count / total_kit_picks * 100) if total_kit_picks > 0 else 0
                lines.append(f"{get_kit_emoji(kit_name) or ''} {kit_name} — **{pct:.0f}%** ({count})")
                rol_chart_items.append((kit_name, pct, "#00FFFF"))
        else:
            lines.append("Sin datos de kits.")

        # Specialization: % of picks in top kit
        if top_kits:
            top_pct = (top_kits[0][1] / total_kit_picks * 100) if total_kit_picks > 0 else 0
            spec = "Especialista" if top_pct > 50 else "Versátil" if top_pct < 25 else "Balanceado"
            lines.append(f"\n📊 **Especialización:** {spec} ({top_pct:.0f}% en {top_kits[0][0]})")

        # Revives/round if medic
        medic_count = normalized.get("Medico", 0)
        if medic_count > 0:
            revives_given = player.get("total_revives_given", 0)
            lines.append(f"💉 **Medic** — Revives/ronda: **{revives_given / rounds:.2f}**")

        # Vehicles destroyed/round if AT/crewman
        at_count = sum(normalized.get(k, 0) for k in ("HAT", "LAT", "Anti-Tanque", "Tripulante"))
        if at_count > 0:
            vehs = player.get("total_vehicles_destroyed", 0)
            lines.append(f"💥 **AT/Tripulante** — Vehículos destruidos/ronda: **{vehs / rounds:.2f}**")

        # Teamwork ratio
        total_score = player.get("total_score", 0)
        tw_score = player.get("total_teamwork_score", 0)
        tw_ratio = (tw_score / total_score) if total_score > 0 else 0
        lines.append(f"\n🤝 Teamwork ratio: **{tw_ratio:.1%}** (tw_score/score)")

        # Color based on specialization
        if medic_count > 0 and medic_count >= total_kit_picks * 0.3:
            color = discord.Color.green()
        elif at_count > 0 and at_count >= total_kit_picks * 0.3:
            color = discord.Color.dark_red()
        else:
            color = discord.Color.blue()

        embed = discord.Embed(
            title=f"🎖️ Análisis de Rol: {player['ign']}",
            description="\n".join(lines),
            color=color,
        )
        embed.set_footer(text=f"Datos de {rounds} rondas | {standard_footer()}")

        if rol_chart_items:
            buf = render_horizontal_bars(rol_chart_items, title=f"Kits - {player['ign']}", max_value=100, value_suffix="%")
            file = discord.File(buf, filename="rol.png")
            embed.set_image(url="attachment://rol.png")
            await ctx.send(embed=embed, file=file)
        else:
            embed.set_thumbnail(url=BOT_THUMBNAIL)
            await ctx.send(embed=embed)

    # ── -winrate <jugador> ────────────────────────────────────────────

    @commands.hybrid_command(
        name="winrate",
        aliases=["wr"],
        description="Análisis de victorias y derrotas de un jugador (datos de demos)",
    )
    @app_commands.describe(jugador="Nombre del jugador")
    @app_commands.autocomplete(jugador=demo_player_autocomplete)
    async def winrate(self, ctx: commands.Context, *, jugador: str):
        if self._check_mode(ctx):
            await ctx.send("⚠️ Estos comandos requieren modo **Demos** o **Combinado**. Usá `-ayuda` para cambiar el modo.")
            return
        data = await self.fetcher.fetch_player_details()
        player = _find_demo_player(data, jugador)

        if not player:
            await ctx.send(f"No se encontró a **{jugador}** en los datos de demos. Jugá algunas partidas más o probá `-buscar <nombre>` para verificar.")
            return

        wins = player.get("wins", 0)
        losses = player.get("losses", 0)
        total_games = wins + losses
        if total_games == 0:
            await ctx.send(
                f"⚠️ **{player.get('ign', jugador)}** aún no tiene datos de winrate. "
                "Los datos se actualizan cada hora, probá más tarde."
            )
            return
        overall_wr = (wins / total_games * 100) if total_games > 0 else 0

        lines = []
        # Overall winrate
        lines.append(f"**Winrate general:** **{overall_wr:.1f}%** ({wins}W / {losses}L)")

        # Per-gamemode: winrate + desempeño (K/D, KPR), nombres legibles
        gm_stats = player.get("gamemode_stats", {})
        if gm_stats:
            lines.append("\n**Por gamemode:**")
            for gm, gs in sorted(gm_stats.items(), key=lambda x: x[1].get("rounds", 0), reverse=True):
                rds = gs.get("rounds", 0)
                w = gs.get("wins", 0)
                wr = gs.get("winrate", (w / rds * 100) if rds else 0)
                kd = gs.get("kd", 0)
                kpr = gs.get("avg_kpr", 0)
                lines.append(
                    f"  **{clean_gamemode(gm)}** — WR **{wr:.0f}%** ({w}W/{rds}R) · "
                    f"K/D **{kd:.2f}** · KPR {kpr:.2f}"
                )
        else:
            # Fallback al esquema viejo si todavía no se regeneró gamemode_stats
            rounds_gm = player.get("rounds_per_gamemode", {})
            wins_gm = player.get("wins_per_gamemode", {})
            if rounds_gm:
                lines.append("\n**Por gamemode:**")
                for gm, rds in sorted(rounds_gm.items(), key=lambda x: x[1], reverse=True):
                    w = wins_gm.get(gm, 0)
                    wr = (w / rds * 100) if rds > 0 else 0
                    lines.append(f"  **{clean_gamemode(gm)}** — **{wr:.0f}%** ({w}W/{rds}R)")

        # Per-faction winrate
        faction_stats = player.get("faction_stats", {})
        if faction_stats:
            lines.append("\n**Por facción:**")
            for faction, fdata in sorted(faction_stats.items(), key=lambda x: x[1].get("rounds", 0), reverse=True):
                f_rounds = fdata.get("rounds", 0)
                f_wins = fdata.get("wins", 0)
                f_wr = (f_wins / f_rounds * 100) if f_rounds > 0 else 0
                lines.append(f"  `{faction}` — **{f_wr:.0f}%** ({f_wins}W/{f_rounds}R)")

        # Stats in wins vs losses
        win_stats = player.get("win_stats", {})
        if win_stats:
            lines.append("\n**Rendimiento en victorias vs derrotas:**")
            w_kills = win_stats.get("avg_kills_in_wins", 0)
            l_kills = win_stats.get("avg_kills_in_losses", 0)
            w_deaths = win_stats.get("avg_deaths_in_wins", 0)
            l_deaths = win_stats.get("avg_deaths_in_losses", 0)
            lines.append(f"  Kills promedio: **{w_kills:.1f}** en W vs **{l_kills:.1f}** en L")
            lines.append(f"  Deaths promedio: **{w_deaths:.1f}** en W vs **{l_deaths:.1f}** en L")

        embed = discord.Embed(
            title=f"📊 Winrate de {player['ign']}",
            description="\n".join(lines),
            color=discord.Color.green() if overall_wr >= 50 else discord.Color.red(),
        )
        embed.set_footer(text=f"Datos de {total_games} partidas | {standard_footer()}")
        embed.set_thumbnail(url=BOT_THUMBNAIL)

        # Build winrate chart
        chart_labels = []
        wr_values = []
        # Add gamemode winrates
        rounds_gm = player.get("rounds_per_gamemode", {})
        wins_gm = player.get("wins_per_gamemode", {})
        for gm, rds in sorted(rounds_gm.items(), key=lambda x: x[1], reverse=True):
            w = wins_gm.get(gm, 0)
            wr = (w / rds * 100) if rds > 0 else 0
            chart_labels.append(gm)
            wr_values.append(wr)
        # Add faction winrates
        faction_stats = player.get("faction_stats", {})
        for faction, fdata in sorted(faction_stats.items(), key=lambda x: x[1].get("rounds", 0), reverse=True):
            f_rounds = fdata.get("rounds", 0)
            f_wins = fdata.get("wins", 0)
            f_wr = (f_wins / f_rounds * 100) if f_rounds > 0 else 0
            chart_labels.append(faction)
            wr_values.append(f_wr)

        if chart_labels:
            buf = render_bar_chart(chart_labels, wr_values, f"Winrate de {player['ign']}", "Categoría", "Winrate %")
            file = discord.File(buf, filename="winrate.png")
            embed.set_image(url="attachment://winrate.png")
        else:
            file = None

        view = ExplainView("winrate")
        if file:
            await ctx.send(embed=embed, file=file, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    # ── -consistencia <jugador> ───────────────────────────────────────

    @commands.hybrid_command(
        name="consistencia",
        aliases=["consistency", "varianza"],
        description="Análisis de consistencia y varianza de un jugador (datos de demos)",
    )
    @app_commands.describe(jugador="Nombre del jugador")
    @app_commands.autocomplete(jugador=demo_player_autocomplete)
    async def consistencia(self, ctx: commands.Context, *, jugador: str):
        if self._check_mode(ctx):
            await ctx.send("⚠️ Estos comandos requieren modo **Demos** o **Combinado**. Usá `-ayuda` para cambiar el modo.")
            return
        data = await self.fetcher.fetch_player_details()
        player = _find_demo_player(data, jugador)

        if not player:
            await ctx.send(f"No se encontró a **{jugador}** en los datos de demos. Jugá algunas partidas más o probá `-buscar <nombre>` para verificar.")
            return

        # Check if enriched fields exist yet
        if "consistency_score" not in player:
            await ctx.send(
                f"⚠️ **{player.get('ign', jugador)}** aún no tiene datos de consistencia. "
                "Los datos se actualizan cada hora, probá más tarde."
            )
            return

        consistency = player.get("consistency_score", -1)
        if consistency == -1:
            await ctx.send(
                f"⚠️ **{player.get('ign', jugador)}** necesita al menos 5 rondas con kills "
                "para calcular consistencia. Seguí jugando y probá después."
            )
            return
        kpr_stddev = player.get("kpr_stddev", 0.0)
        avg_kpr = player.get("avg_kpr", 0.0)
        coeff_var = (kpr_stddev / avg_kpr * 100) if avg_kpr > 0 else 0

        # Category
        if consistency >= 80:
            category = "Muy consistente"
            color = discord.Color.green()
        elif consistency >= 60:
            category = "Consistente"
            color = discord.Color.green()
        elif consistency >= 40:
            category = "Variable"
            color = discord.Color.gold()
        else:
            category = "Muy variable"
            color = discord.Color.red()

        lines = [
            f"**Consistencia:** **{consistency:.0f}/100** — {category}",
            f"\n📈 **Varianza de KPR:**",
            f"  Desviación estándar: **{kpr_stddev:.2f}**",
            f"  KPR promedio: **{avg_kpr:.2f}**",
            f"  Coeficiente de variación: **{coeff_var:.1f}%**",
        ]

        # Best and worst round
        best_round = player.get("best_round", {})
        worst_round = player.get("worst_round", {})
        if best_round:
            br_map = best_round.get("map", "N/A")
            br_kills = best_round.get("kills", 0)
            br_deaths = best_round.get("deaths", 0)
            lines.append(f"\n🏆 **Mejor ronda:** {br_map} — {br_kills}K / {br_deaths}D")
        if worst_round:
            wr_map = worst_round.get("map", "N/A")
            wr_kills = worst_round.get("kills", 0)
            wr_deaths = worst_round.get("deaths", 0)
            lines.append(f"💀 **Peor ronda:** {wr_map} — {wr_kills}K / {wr_deaths}D")

        # % rounds above average
        pct_above = player.get("pct_rounds_above_avg", 0.0)
        lines.append(f"\n📊 Rondas sobre el promedio: **{pct_above:.0f}%**")

        # Streaks
        win_streak = player.get("longest_win_streak", 0)
        loss_streak = player.get("longest_loss_streak", 0)
        lines.append(f"🔥 Mayor racha de victorias: **{win_streak}**")
        lines.append(f"❄️ Mayor racha de derrotas: **{loss_streak}**")

        embed = discord.Embed(
            title=f"📉 Consistencia de {player['ign']}",
            description="\n".join(lines),
            color=color,
        )
        embed.set_footer(text=f"Datos de {player.get('rounds_played', 0)} rondas | {standard_footer()}")

        cons_items = [("Consistencia", consistency, "#00FF88")]
        buf = render_horizontal_bars(cons_items, title=f"Consistencia - {player['ign']}", max_value=100)
        file = discord.File(buf, filename="consistencia.png")
        embed.set_image(url="attachment://consistencia.png")

        view = ExplainView("consistencia")
        await ctx.send(embed=embed, file=file, view=view)

    # ── -mapa_perfil <jugador> ────────────────────────────────────────

    @commands.hybrid_command(
        name="mapa_perfil",
        aliases=["map_profile", "mapas"],
        description="Rendimiento por mapa de un jugador (datos de demos)",
    )
    @app_commands.describe(jugador="Nombre del jugador")
    @app_commands.autocomplete(jugador=demo_player_autocomplete)
    async def mapa_perfil(self, ctx: commands.Context, *, jugador: str):
        if self._check_mode(ctx):
            await ctx.send("⚠️ Estos comandos requieren modo **Demos** o **Combinado**. Usá `-ayuda` para cambiar el modo.")
            return
        data = await self.fetcher.fetch_player_details()
        player = _find_demo_player(data, jugador)

        if not player:
            await ctx.send(f"No se encontró a **{jugador}** en los datos de demos. Jugá algunas partidas más o probá `-buscar <nombre>` para verificar.")
            return

        # per_map_stats has detailed data; maps_played is fallback (just round counts)
        map_stats = player.get("per_map_stats", {})
        maps_played = player.get("maps_played", {})
        if not map_stats and not maps_played:
            await ctx.send(f"**{player.get('ign', jugador)}** no tiene datos de mapas registrados.")
            return

        # Build list of (map_name, avg_kpr, rounds, wins)
        map_data = []
        if map_stats:
            for m_name, m_info in map_stats.items():
                m_rounds = m_info.get("rounds", 0)
                m_avg_kpr = m_info.get("avg_kpr", 0.0)
                m_wins = m_info.get("wins", 0)
                map_data.append((m_name, m_avg_kpr, m_rounds, m_wins))
        elif maps_played:
            # Fallback: only round counts, no KPR/wins
            for m_name, m_rounds in maps_played.items():
                map_data.append((m_name, 0.0, m_rounds, 0))

        embed = discord.Embed(
            title=f"🗺️ Perfil por Mapa: {player['ign']}",
            color=discord.Color.purple(),
        )

        # Top 5 maps by avg KPR
        top_maps = sorted(map_data, key=lambda x: x[1], reverse=True)[:5]
        map_chart_items = []
        if top_maps:
            lines = []
            for m_name, m_kpr, m_rds, m_wins in top_maps:
                m_wr = (m_wins / m_rds * 100) if m_rds > 0 else 0
                lines.append(f"**{clean_map_name(m_name)}** — KPR: **{m_kpr:.2f}** | WR: {m_wr:.0f}% ({m_rds}R)")
                map_chart_items.append((clean_map_name(m_name), m_kpr, "#00FF88"))
            embed.add_field(name="🏆 Top 5 Mapas (por KPR)", value="\n".join(lines), inline=False)

        # Bottom 3 maps by avg KPR (min 3 rounds)
        qualified = [m for m in map_data if m[2] >= 3]
        bottom_maps = sorted(qualified, key=lambda x: x[1])[:3]
        if bottom_maps:
            lines = []
            for m_name, m_kpr, m_rds, m_wins in bottom_maps:
                m_wr = (m_wins / m_rds * 100) if m_rds > 0 else 0
                lines.append(f"**{clean_map_name(m_name)}** — KPR: **{m_kpr:.2f}** | WR: {m_wr:.0f}% ({m_rds}R)")
                map_chart_items.append((clean_map_name(m_name), m_kpr, "#FF4444"))
            embed.add_field(name="📉 Peores Mapas (por KPR, min 3R)", value="\n".join(lines), inline=False)

        # Most played maps
        most_played = sorted(map_data, key=lambda x: x[2], reverse=True)[:5]
        if most_played:
            lines = []
            for m_name, m_kpr, m_rds, _ in most_played:
                lines.append(f"**{clean_map_name(m_name)}** — **{m_rds}** rondas (KPR: {m_kpr:.2f})")
            embed.add_field(name="📊 Más Jugados", value="\n".join(lines), inline=False)

        # Preferred gamemode breakdown
        rounds_gm = player.get("rounds_per_gamemode", {})
        if rounds_gm:
            total_gm = sum(rounds_gm.values())
            gm_lines = []
            for gm, count in sorted(rounds_gm.items(), key=lambda x: x[1], reverse=True):
                pct = (count / total_gm * 100) if total_gm > 0 else 0
                gm_lines.append(f"`{gm}` — **{pct:.0f}%** ({count}R)")
            embed.add_field(name="🎮 Gamemodes", value="\n".join(gm_lines), inline=False)

        embed.set_footer(text=f"Datos de {player.get('rounds_played', 0)} rondas | {standard_footer()}")

        if map_chart_items:
            buf = render_horizontal_bars(map_chart_items, title=f"KPR por Mapa - {player['ign']}")
            file = discord.File(buf, filename="mapa_perfil.png")
            embed.set_image(url="attachment://mapa_perfil.png")
            await ctx.send(embed=embed, file=file)
        else:
            embed.set_thumbnail(url=BOT_THUMBNAIL)
            await ctx.send(embed=embed)

    # ── -teamwork <jugador> ───────────────────────────────────────────

    @commands.hybrid_command(
        name="teamwork",
        aliases=["tw"],
        description="Análisis de contribución al equipo de un jugador (datos de demos)",
    )
    @app_commands.describe(jugador="Nombre del jugador")
    @app_commands.autocomplete(jugador=demo_player_autocomplete)
    async def teamwork(self, ctx: commands.Context, *, jugador: str):
        if self._check_mode(ctx):
            await ctx.send("⚠️ Estos comandos requieren modo **Demos** o **Combinado**. Usá `-ayuda` para cambiar el modo.")
            return
        data = await self.fetcher.fetch_player_details()
        player = _find_demo_player(data, jugador)

        if not player:
            await ctx.send(f"No se encontró a **{jugador}** en los datos de demos. Jugá algunas partidas más o probá `-buscar <nombre>` para verificar.")
            return

        rounds = player.get("rounds_played", 1)
        total_score = player.get("total_score", 0)
        tw_score = player.get("total_teamwork_score", 0)
        tw_ratio = (tw_score / total_score) if total_score > 0 else 0

        revives = player.get("total_revives_given", 0)
        flags = player.get("total_flags_captured", 0)
        vehs_destroyed = player.get("total_vehicles_destroyed", 0)

        revives_per_round = revives / rounds
        flags_per_round = flags / rounds
        vehs_per_round = vehs_destroyed / rounds

        # Category
        if tw_ratio >= 0.5:
            tw_cat = "Excelente"
        elif tw_ratio >= 0.35:
            tw_cat = "Bueno"
        elif tw_ratio >= 0.2:
            tw_cat = "Moderado"
        else:
            tw_cat = "Bajo"

        # Teamwork Index: weighted combo (normalized)
        # Benchmarks for normalization
        bench_tw_ratio = 0.35
        bench_revives = 1.0   # per round
        bench_flags = 0.5     # per round

        norm_tw = min(tw_ratio / bench_tw_ratio, 1.0) if bench_tw_ratio > 0 else 0
        norm_rev = min(revives_per_round / bench_revives, 1.0) if bench_revives > 0 else 0
        norm_flags = min(flags_per_round / bench_flags, 1.0) if bench_flags > 0 else 0

        tw_index = (0.4 * norm_tw + 0.3 * norm_rev + 0.3 * norm_flags) * 100

        lines = [
            f"**Teamwork ratio:** **{tw_ratio:.1%}** — {tw_cat}",
            f"  TW Score: {format_number(tw_score)} / Total Score: {format_number(total_score)}",
            "",
            f"💉 Revives/ronda: **{revives_per_round:.2f}** (benchmark: {bench_revives:.1f})",
            f"🚩 Flags/ronda: **{flags_per_round:.2f}** (benchmark: {bench_flags:.1f})",
            f"💥 Vehículos destruidos/ronda: **{vehs_per_round:.2f}**",
            "",
            f"**Teamwork Index:** **{tw_index:.0f}/100**",
            f"  (40% tw_ratio + 30% revives + 30% flags, normalizado)",
        ]

        # % de rondas jugadas en escuadra (vs lobo solitario). Solo rondas nuevas
        # traen el dato de escuadra, por eso el denominador es aparte.
        sq_rounds = player.get("rounds_with_squad_data", 0)
        if sq_rounds:
            sq_pct = player.get("rounds_in_squad", 0) / sq_rounds * 100
            lines.append(f"👥 En escuadra: **{sq_pct:.0f}%** de las rondas ({sq_rounds} con dato)")
        # Cohesión de escuadra: distancia media al centroide de su squad (menor = más juntos).
        coh_n = player.get("cohesion_samples", 0)
        if coh_n >= 20:
            coh = player.get("cohesion_sum", 0) / coh_n
            label = ("muy unida" if coh < 150 else "unida" if coh < 300
                     else "dispersa" if coh < 600 else "muy dispersa")
            lines.append(f"🧭 Cohesión de escuadra: **{label}** ({coh:.0f}m al centro)")

        # Compare vs benchmarks
        lines.append("\n**Comparación vs benchmark:**")
        lines.append(f"  TW Ratio: {'✅' if tw_ratio >= bench_tw_ratio else '❌'} {tw_ratio:.1%} vs {bench_tw_ratio:.0%}")
        lines.append(f"  Revives/R: {'✅' if revives_per_round >= bench_revives else '❌'} {revives_per_round:.2f} vs {bench_revives:.1f}")
        lines.append(f"  Flags/R: {'✅' if flags_per_round >= bench_flags else '❌'} {flags_per_round:.2f} vs {bench_flags:.1f}")

        # Color: blue/gold theme
        color = discord.Color.gold() if tw_index >= 60 else discord.Color.blue()

        tw_chart_items = [
            ("TW Ratio", tw_ratio * 100, "#00FFFF"),
            ("TW Index", tw_index, "#FFD700"),
        ]
        buf = render_horizontal_bars(tw_chart_items, title=f"Teamwork - {player['ign']}", max_value=100)
        file = discord.File(buf, filename="teamwork.png")

        embed = discord.Embed(
            title=f"🤝 Teamwork de {player['ign']}",
            description="\n".join(lines),
            color=color,
        )
        embed.set_image(url="attachment://teamwork.png")
        embed.set_footer(text=f"Datos de {rounds} rondas | {standard_footer()}")
        view = ExplainView("teamwork")
        await ctx.send(embed=embed, file=file, view=view)

    # ── -combate <jugador> ────────────────────────────────────────────

    @commands.hybrid_command(
        name="combate",
        aliases=["combat", "ritmo"],
        description="Ritmo y combate: racha, clutch, first blood, vida promedio, disciplina (demos)",
    )
    @app_commands.describe(jugador="Nombre del jugador")
    @app_commands.autocomplete(jugador=demo_player_autocomplete)
    async def combate(self, ctx: commands.Context, *, jugador: str):
        """Métricas de combate fino extraídas de las demos: rachas, clutch, first
        blood, vida promedio, kills/min y disciplina (teamkills/suicidios)."""
        if self._check_mode(ctx):
            await ctx.send("⚠️ Estos comandos requieren modo **Demos** o **Combinado**. Usá `-ayuda` para cambiar el modo.")
            return
        data = await self.fetcher.fetch_player_details()
        player = _find_demo_player(data, jugador)
        if not player:
            await ctx.send(f"No se encontró a **{jugador}** en los datos de demos. Jugá algunas partidas más o probá `-buscar <nombre>` para verificar.")
            return

        streak = player.get("best_killstreak", 0)
        clutch = player.get("total_clutch_kills", 0)
        first_bloods = player.get("total_first_bloods", 0)
        teamkills = player.get("total_teamkills", 0)
        suicides = player.get("total_suicides_demo", 0)
        alive_s = player.get("alive_seconds", 0)
        lives = player.get("lives", 0)
        total_kills = player.get("total_kills", 0)

        # Estas métricas se acumulan desde las rondas nuevas (parser actualizado).
        has_data = any((streak, clutch, first_bloods, teamkills, suicides, lives))
        if not has_data:
            await ctx.send(
                f"⏳ **{player['ign']}** todavía no tiene métricas de combate fino. "
                "Se calculan desde las partidas nuevas — probá en unos días."
            )
            return

        def _mmss(s):
            s = int(s)
            return f"{s // 60}m {s % 60:02d}s"

        lines = []
        # ⏱️ Ritmo
        if lives:
            avg_life = alive_s / lives
            kpm_alive = total_kills / (alive_s / 60) if alive_s else 0
            lines.append(f"⏱️ **Vida promedio:** {_mmss(avg_life)} ({lives} vidas)")
            lines.append(f"🎯 **Kills/min (con vida):** {kpm_alive:.2f}")
        # 🔥 Highlights
        lines.append(f"🔥 **Mejor racha:** {streak} kills sin morir")
        if first_bloods:
            lines.append(f"🩸 **First bloods:** {first_bloods}")
        if clutch:
            lines.append(f"💥 **Kills clutch:** {clutch} (con el equipo a <25 tickets)")
        # 🎖️ Disciplina
        disc = []
        if teamkills:
            disc.append(f"🔫 Teamkills: **{teamkills}**")
        if suicides:
            disc.append(f"💀 Suicidios: **{suicides}**")
        if disc:
            lines.append("🎖️ **Disciplina:** " + " · ".join(disc))

        embed = discord.Embed(
            title=f"⚔️ Combate de {player['ign']}",
            description="\n".join(lines),
            color=discord.Color.dark_red(),
        )
        embed.set_thumbnail(url=BOT_THUMBNAIL)
        embed.set_footer(text=f"Datos de {player['rounds_played']} rondas | {standard_footer()}")
        await ctx.send(embed=embed)

    # ── -sinergia <jugador> ───────────────────────────────────────────

    @commands.hybrid_command(
        name="sinergia",
        aliases=["synergy", "duo"],
        description="Con qué compañeros de escuadra rendís mejor/peor (datos de demos)",
    )
    @app_commands.describe(jugador="Nombre del jugador")
    @app_commands.autocomplete(jugador=demo_player_autocomplete)
    async def sinergia(self, ctx: commands.Context, *, jugador: str):
        """Sinergia de dúo: impacto en tu KPR y winrate al jugar en la misma escuadra
        que cada compañero frecuente."""
        if self._check_mode(ctx):
            await ctx.send("⚠️ Estos comandos requieren modo **Demos** o **Combinado**. Usá `-ayuda` para cambiar el modo.")
            return
        await ctx.defer()
        synergy = await self.fetcher.fetch_synergy()
        if not synergy:
            await ctx.send("⏳ La sinergia se calcula desde las partidas nuevas (con datos de escuadra). Probá en unos días.")
            return

        # Resolver el nombre canónico (mismas reglas que el resto de comandos).
        entry = synergy.get(jugador)
        name = jugador
        if entry is None:
            match = find_player([{"Player": k} for k in synergy], jugador)
            if match:
                name = match["Player"]
                entry = synergy.get(name)

        if not entry or not entry.get("mates"):
            await ctx.send(
                f"No hay datos de sinergia para **{jugador}** todavía. Se necesitan rondas "
                "jugando en escuadra con compañeros recurrentes (se acumulan desde las partidas nuevas)."
            )
            return

        baseline = entry["baseline"]
        base_rounds = baseline.get("rounds", 0)
        base_kills = baseline.get("kills", 0)
        base_kpr = base_kills / base_rounds if base_rounds else 0

        rows = []
        for q, v in entry["mates"].items():
            r = v.get("rounds", 0)
            if r < 3:  # mínimo para que sea representativo
                continue
            kpr_with = v.get("kills", 0) / r
            wo_r = base_rounds - r
            kpr_wo = (base_kills - v.get("kills", 0)) / wo_r if wo_r > 0 else base_kpr
            impact = kpr_with - kpr_wo
            wr = v.get("wins", 0) / r * 100
            rows.append((impact, q, r, kpr_with, kpr_wo, wr))

        if not rows:
            await ctx.send(
                f"**{name}** todavía no tiene compañeros con suficientes rondas compartidas "
                "(mínimo 3). Seguí jugando en escuadra y probá después."
            )
            return

        rows.sort(reverse=True)
        best = rows[:5]
        worst = [r for r in rows if r[0] < 0][-3:]

        def _line(row):
            impact, q, r, kpr_with, kpr_wo, wr = row
            sign = "📈" if impact >= 0 else "📉"
            return (f"{sign} **{q}** — KPR **{kpr_with:.2f}** (solo {kpr_wo:.2f}, "
                    f"{impact:+.2f}) · WR {wr:.0f}% · {r} rondas")

        embed = discord.Embed(
            title=f"🤝 Sinergia de {name}",
            description=(
                "Rendimiento jugando en la **misma escuadra** que cada compañero.\n"
                f"KPR base (en escuadra): **{base_kpr:.2f}** · {base_rounds} rondas con dato"
            ),
            color=discord.Color.teal(),
        )
        embed.add_field(
            name="🟢 Mejores compañeros (más impacto en tu KPR)",
            value="\n".join(_line(r) for r in best),
            inline=False,
        )
        if worst:
            embed.add_field(
                name="🔴 Rendís menos con",
                value="\n".join(_line(r) for r in reversed(worst)),
                inline=False,
            )
        embed.set_thumbnail(url=BOT_THUMBNAIL)
        embed.set_footer(text=standard_footer())
        await ctx.send(embed=embed)

    # ── -clan_fortalezas <clan> ───────────────────────────────────────

    @commands.hybrid_command(
        name="clan_fortalezas",
        aliases=["clan_foda", "clan_analysis"],
        description="Análisis SWOT de un clan (datos de demos)",
    )
    @app_commands.describe(clan="Nombre del clan")
    async def clan_fortalezas(self, ctx: commands.Context, *, clan: str):
        if self._check_mode(ctx):
            await ctx.send("⚠️ Estos comandos requieren modo **Demos** o **Combinado**. Usá `-ayuda` para cambiar el modo.")
            return
        data = await self.fetcher.fetch_player_details()

        # Get clan members from prstats (the source of truth for clan membership)
        try:
            prstats = await self.fetcher.fetch_all_players()
        except Exception:
            prstats = []

        clan_upper = clan.upper()
        # Build set of player names that belong to this clan (from prstats)
        clan_member_names = set()
        resolved_clan_name = clan_upper
        for p in prstats:
            if p.get("Clan", "").upper() == clan_upper:
                clan_member_names.add(p["Player"].lower())
                resolved_clan_name = p.get("Clan", clan_upper)

        if not clan_member_names:
            await ctx.send(f"No se encontró el clan **{clan}** en los datos de prstats.")
            return

        # Match demo players to clan members
        clan_players = []
        for p in data:
            p_ign = p.get("ign", "").lower()
            if p_ign in clan_member_names:
                clan_players.append(p)

        if not clan_players:
            await ctx.send(
                f"No se encontraron jugadores de **{resolved_clan_name}** en los datos de demos. "
                "Los datos se acumulan con cada corrida del scraper."
            )
            return

        n = len(clan_players)

        # Average stats across members
        def avg_field(field: str, default=0):
            vals = [p.get(field, default) for p in clan_players]
            return sum(vals) / n if n > 0 else 0

        avg_kills = avg_field("total_kills") / max(avg_field("rounds_played", 1), 1)
        avg_tw_ratio_vals = []
        for p in clan_players:
            ts = p.get("total_score", 0)
            tw = p.get("total_teamwork_score", 0)
            avg_tw_ratio_vals.append((tw / ts) if ts > 0 else 0)
        avg_tw_ratio = sum(avg_tw_ratio_vals) / n if n > 0 else 0

        avg_wr_vals = []
        for p in clan_players:
            w = p.get("wins", 0)
            l = p.get("losses", 0)
            total = w + l
            avg_wr_vals.append((w / total * 100) if total > 0 else 0)
        avg_winrate = sum(avg_wr_vals) / n if n > 0 else 0

        avg_consistency = avg_field("consistency_score", 50)

        # All-clan averages (compute from ALL players for comparison)
        all_n = len(data) if data else 1
        all_kills = sum(p.get("total_kills", 0) for p in data) / max(sum(p.get("rounds_played", 1) for p in data), 1) if data else 0
        all_tw_ratios = []
        for p in data:
            ts = p.get("total_score", 0)
            tw = p.get("total_teamwork_score", 0)
            all_tw_ratios.append((tw / ts) if ts > 0 else 0)
        all_avg_tw = sum(all_tw_ratios) / all_n if all_tw_ratios else 0

        all_wr_vals = []
        for p in data:
            w = p.get("wins", 0)
            l = p.get("losses", 0)
            total = w + l
            all_wr_vals.append((w / total * 100) if total > 0 else 0)
        all_avg_wr = sum(all_wr_vals) / all_n if all_wr_vals else 0
        all_avg_consistency = sum(p.get("consistency_score", 50) for p in data) / all_n if data else 50

        # Also get avg deaths/round for the clan
        avg_deaths = avg_field("total_deaths") / max(avg_field("rounds_played", 1), 1)
        all_deaths = sum(p.get("total_deaths", 0) for p in data) / max(sum(p.get("rounds_played", 1) for p in data), 1) if data else 0
        avg_revives = avg_field("total_revives_given") / max(avg_field("rounds_played", 1), 1)
        all_revives = sum(p.get("total_revives_given", 0) for p in data) / max(sum(p.get("rounds_played", 1) for p in data), 1) if data else 0

        # Identify strongest and weakest metric
        metrics = {
            "Kills por ronda": (avg_kills, all_kills),
            "Trabajo en equipo": (avg_tw_ratio, all_avg_tw),
            "Tasa de victoria": (avg_winrate, all_avg_wr),
            "Consistencia": (avg_consistency, all_avg_consistency),
        }

        diffs = {}
        for m_name, (clan_val, global_val) in metrics.items():
            if global_val > 0:
                diffs[m_name] = (clan_val - global_val) / global_val
            else:
                diffs[m_name] = 0

        strongest = max(diffs, key=diffs.get)
        weakest = min(diffs, key=diffs.get)

        # Helper for comparison arrows
        def _cmp(clan_val, global_val):
            if clan_val > global_val * 1.05:
                return "🟢"
            elif clan_val < global_val * 0.95:
                return "🔴"
            return "🟡"

        # Build embed with structured fields
        embed = discord.Embed(
            title=f"📋 Análisis del Clan {resolved_clan_name}",
            description=f"**{n}** jugadores con datos de demos · **{int(avg_field('rounds_played'))}** rondas promedio",
            color=discord.Color.gold(),
        )

        # Combat metrics
        embed.add_field(
            name="⚔️ Combate",
            value=(
                f"{_cmp(avg_kills, all_kills)} **Kills/ronda:** {avg_kills:.2f} (promedio global: {all_kills:.2f})\n"
                f"{_cmp(all_deaths, avg_deaths)} **Muertes/ronda:** {avg_deaths:.2f} (global: {all_deaths:.2f})\n"
                f"{_cmp(avg_revives, all_revives)} **Revives/ronda:** {avg_revives:.2f} (global: {all_revives:.2f})"
            ),
            inline=False,
        )

        # Team play metrics
        has_wr_data = any((p.get("wins", 0) + p.get("losses", 0)) > 0 for p in clan_players)
        wr_text = f"**{avg_winrate:.1f}%** (global: {all_avg_wr:.1f}%)" if has_wr_data else "*Datos insuficientes*"

        embed.add_field(
            name="🤝 Trabajo en Equipo",
            value=(
                f"{_cmp(avg_tw_ratio, all_avg_tw)} **Teamwork / Score total:** {avg_tw_ratio:.0%} (global: {all_avg_tw:.0%})\n"
                f"🏆 **Tasa de victoria:** {wr_text}\n"
                f"{_cmp(avg_consistency, all_avg_consistency)} **Consistencia:** {avg_consistency:.0f}/100 (global: {all_avg_consistency:.0f})"
            ),
            inline=False,
        )

        # Strengths & weaknesses
        s_emoji = "💪" if diffs[strongest] > 0 else "📊"
        w_emoji = "⚠️" if diffs[weakest] < 0 else "📊"
        s_pct = diffs[strongest] * 100
        w_pct = diffs[weakest] * 100
        embed.add_field(
            name=f"{s_emoji} Mayor fortaleza",
            value=f"**{strongest}** ({'+' if s_pct > 0 else ''}{s_pct:.0f}% vs promedio global)",
            inline=True,
        )
        embed.add_field(
            name=f"{w_emoji} Mayor debilidad",
            value=f"**{weakest}** ({'+' if w_pct > 0 else ''}{w_pct:.0f}% vs promedio global)",
            inline=True,
        )

        # Kit distribution (normalized)
        raw_kit_totals: dict[str, int] = {}
        for p in clan_players:
            for kit, count in p.get("kits_used", {}).items():
                raw_kit_totals[kit] = raw_kit_totals.get(kit, 0) + count
        kit_totals = normalize_kits(raw_kit_totals)
        total_kit_picks = sum(kit_totals.values()) if kit_totals else 0
        if kit_totals:
            kit_lines = []
            for kit_name, count in sorted(kit_totals.items(), key=lambda x: x[1], reverse=True)[:7]:
                pct = (count / total_kit_picks * 100) if total_kit_picks > 0 else 0
                emoji = get_kit_emoji(kit_name)
                label = f"{emoji} {kit_name}" if emoji else kit_name
                kit_lines.append(f"**{pct:.0f}%** — {label}")
            embed.add_field(
                name="🎖️ Kits más usados",
                value="\n".join(kit_lines),
                inline=False,
            )

        # Skill spread: top vs bottom players
        kpr_vals = []
        for p in clan_players:
            rds = p.get("rounds_played", 1)
            k = p.get("total_kills", 0)
            kpr_vals.append((p.get("ign", "?"), k / rds if rds > 0 else 0))
        kpr_vals.sort(key=lambda x: x[1], reverse=True)
        if len(kpr_vals) >= 2:
            top_name, top_kpr = kpr_vals[0]
            bot_name, bot_kpr = kpr_vals[-1]
            spread = top_kpr - bot_kpr
            dependencia = "Alta (dependen de pocos)" if spread > 3 else "Media" if spread > 1.5 else "Baja (clan parejo)"
            embed.add_field(
                name="📏 Dispersión de nivel",
                value=(
                    f"🥇 **{top_name}** — {top_kpr:.2f} kills/ronda\n"
                    f"📉 **{bot_name}** — {bot_kpr:.2f} kills/ronda\n"
                    f"Diferencia: **{spread:.2f}** · Dependencia: **{dependencia}**"
                ),
                inline=False,
            )

        embed.set_footer(text=standard_footer())
        embed.set_thumbnail(url=BOT_THUMBNAIL)

        # Build multi comparison chart
        metric_labels = ["Kills/ronda", "Teamwork", "Winrate", "Consistencia"]
        clan_vals = [avg_kills, avg_tw_ratio * 100, avg_winrate, avg_consistency]
        global_vals = [all_kills, all_avg_tw * 100, all_avg_wr, all_avg_consistency]
        title = f"Análisis del Clan {resolved_clan_name}"
        buf = render_multi_comparison(resolved_clan_name, clan_vals, "Global", global_vals, metric_labels, title)
        file = discord.File(buf, filename="clan_fortalezas.png")
        embed.set_image(url="attachment://clan_fortalezas.png")

        view = ExplainView("clan_fortalezas")
        await ctx.send(embed=embed, file=file, view=view)

    # ── -top_periodo <periodo> [cantidad] [metrica] ────────────────────

    @commands.hybrid_command(
        name="top_periodo",
        aliases=["top_semana", "top_mes", "top_dia", "top_week", "top_month", "top_day", "top_time"],
        description="Ranking de jugadores en un período de tiempo (datos de demos)",
    )
    @app_commands.describe(
        periodo="Período: dia/semana/mes/todo",
        cantidad="Cantidad de jugadores a mostrar (default: 15)",
        metrica="Métrica: kills, kd, score, revives, teamwork (default: kills)",
    )
    @app_commands.choices(
        periodo=[
            app_commands.Choice(name="Hoy", value="dia"),
            app_commands.Choice(name="Semana", value="semana"),
            app_commands.Choice(name="Mes", value="mes"),
            app_commands.Choice(name="Todo", value="todo"),
        ],
        metrica=[
            app_commands.Choice(name="Kills", value="kills"),
            app_commands.Choice(name="K/D", value="kd"),
            app_commands.Choice(name="Score", value="score"),
            app_commands.Choice(name="Revives", value="revives"),
            app_commands.Choice(name="Teamwork", value="teamwork"),
        ],
    )
    async def top_periodo(
        self,
        ctx: commands.Context,
        periodo: str = "semana",
        cantidad: int = 15,
        metrica: str = "kills",
    ):
        """Ranking de jugadores de clanes en un período de tiempo."""
        if self._check_mode(ctx):
            await ctx.send("⚠️ Este comando requiere modo **Demos** o **Combinado**.")
            return

        # Resolve period from alias if invoked via alias
        invoked = ctx.invoked_with.lower() if ctx.invoked_with else ""
        if "semana" in invoked or "week" in invoked:
            periodo = "semana"
        elif "mes" in invoked or "month" in invoked:
            periodo = "mes"
        elif "dia" in invoked or "day" in invoked:
            periodo = "dia"

        # Map the (possibly aliased) period to its canonical leaderboard file.
        period_file = {
            "dia": "dia", "hoy": "dia", "day": "dia",
            "semana": "semana", "week": "semana", "semanal": "semana",
            "mes": "mes", "month": "mes", "mensual": "mes",
            "todo": "todo", "all": "todo",
        }.get(periodo.lower(), "semana")

        cantidad = max(1, min(cantidad, 50))

        await ctx.defer()

        view = LeaderboardView(
            self.fetcher,
            period=period_file,
            metric=metrica.lower(),
            count=cantidad,
            author_id=ctx.author.id,
        )
        await view.load()
        view.message = await ctx.send(view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DetailedStats(bot))
