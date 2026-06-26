"""Player Hub — vista unificada de un jugador con un dropdown de tabs
(Estadísticas, Perfil, Historial, Resumen demos, Vehículos, Kits, Assets).

Los comandos siguen existiendo como atajos, pero adjuntan este `PlayerHubView` para
saltar entre vistas sin re-tipear. Patrón: como `_HelpSelect` en help_view.py (un Select
que edita el mensaje). Cada tab es un builder async que devuelve `(embed, file|None)`.

El hub es clásico (View + Select + embed + file), no Components V2 — así reusa los embeds
de los comandos. `-estadisticas` mantiene su PlayerCard (Components V2) standalone; acá su
tab es una versión embed compacta.
"""

from __future__ import annotations

import logging

import discord

from bot.config import BOT_THUMBNAIL, performance_color
from bot.services.chart_renderer import render_horizontal_bars, render_radar_chart
from bot.services.history_chart import build_history_embed
from bot.assets.kit_mapping import (
    normalize_kits, get_kit_emoji, clean_vehicle_name, weapon_vehicle_name,
    weapon_vclass, is_vehicle_kill, clean_seat, weapon_category, clean_weapon_name,
)
from bot.assets.vehicle_mapping import get_vehicle_emoji_by_name
from bot.utils import (
    find_player, standard_footer, format_number, get_player_radar,
    get_player_archetype, tier_emoji, _tier_name,
)

logger = logging.getLogger(__name__)


# ── Helpers (locales para evitar import circular con los cogs) ─────────────────
def _top_named(d, namer, n=10, exclude=None):
    agg: dict = {}
    for code, cnt in (d or {}).items():
        if exclude and exclude(code):
            continue
        nm = namer(code)
        agg[nm] = agg.get(nm, 0) + cnt
    return sorted(agg.items(), key=lambda x: x[1], reverse=True)[:n]


def _find_demo(data, name):
    return find_player(data, name, key="ign")


def _veh_emoji(v):
    e = get_vehicle_emoji_by_name(v)
    return f"{e} " if e else ""


def _notfound(name, demos=False):
    where = "los datos de demos (jugá algunas partidas más)" if demos else "la base de datos"
    return (discord.Embed(description=f"No se encontró a **{name}** en {where}.",
                          color=discord.Color.greyple()), None)


# ── Builders: cada uno → (embed, file|None) ───────────────────────────────────
async def build_estadisticas(name, bot):
    data = await bot.data_fetcher.fetch_all_players()
    p = find_player(data, name)
    if not p:
        return _notfound(name)
    ps = p.get("Performance Score", 0)
    try:
        tc = await bot.data_fetcher.fetch_tier_config()
        thr = tc.get("thresholds") if isinstance(tc, dict) else None
    except Exception:
        thr = None
    se, sn = get_player_archetype(p)
    embed = discord.Embed(
        title=f"📊 {p.get('Player', name)}",
        description=f"{tier_emoji(ps, thr)} **{_tier_name(ps, thr)}** · {se} {sn} · `{p.get('Clan', '—')}`",
        color=performance_color(ps, thr),
    )
    embed.add_field(name="Combate", value=(
        f"💥 K/D `{p.get('K/D Ratio', 0):.2f}`\n"
        f"🔫 KPR `{p.get('Kills per Round', 0):.2f}`\n"
        f"🎯 SPR `{p.get('Score per Round', 0):.2f}`"), inline=True)
    embed.add_field(name="Volumen", value=(
        f"☠️ {format_number(p.get('Total Kills', 0))} kills\n"
        f"💀 {format_number(p.get('Total Deaths', 0))} muertes\n"
        f"🎮 {format_number(p.get('Rounds', 0))} rondas"), inline=True)
    embed.add_field(name="🌟 Performance", value=f"**{ps:.2f}**", inline=True)
    embed.set_thumbnail(url=BOT_THUMBNAIL)
    embed.set_footer(text=standard_footer(p))
    return embed, None


async def build_perfil(name, bot):
    data = await bot.data_fetcher.fetch_all_players()
    p = find_player(data, name)
    if not p:
        return _notfound(name)
    clan = p.get("Clan", "N/A")
    radar = get_player_radar(p)
    if not radar:
        return (discord.Embed(title=f"🎯 Perfil — {p.get('Player', name)}",
                              description="Radar no disponible todavía (faltan datos).",
                              color=discord.Color.blurple()), None)
    keys = ["letalidad", "supervivencia", "teamwork", "impacto", "consistencia", "versatilidad"]
    labels = {"letalidad": "Letalidad", "supervivencia": "Supervivencia", "teamwork": "Teamwork",
              "impacto": "Impacto", "consistencia": "Consistencia", "versatilidad": "Versatilidad"}
    player_values = {labels[k]: radar.get(k, 0) for k in keys}
    clan_players = [q for q in data if q.get("Clan") == clan and q.get("radar")]
    if clan_players:
        clan_avg = {labels[k]: sum(q["radar"].get(k, 0) for q in clan_players) / len(clan_players) for k in keys}
    else:
        clan_avg = {labels[k]: 0 for k in keys}
    buf = render_radar_chart(player_values, clan_avg, p.get("Player", name), clan)
    embed = discord.Embed(title=f"🎯 Perfil — {p.get('Player', name)}", color=discord.Color.blurple())
    embed.set_image(url="attachment://radar_perfil.png")
    embed.set_footer(text=standard_footer(p))
    return embed, discord.File(buf, filename="radar_perfil.png")


async def build_historial(name, bot):
    embed, file = await build_history_embed(bot.data_fetcher, name)
    if embed is None:
        return (discord.Embed(description=f"Sin historial para **{name}** todavía.",
                              color=discord.Color.greyple()), None)
    return embed, file


async def build_resumen(name, bot):
    data = await bot.data_fetcher.fetch_player_details()
    player = _find_demo(data, name)
    if not player:
        return _notfound(name, demos=True)
    from bot.views.demo_details import DemoDetailsView
    return DemoDetailsView(name, bot)._build_embed(player), None


async def build_vehiculos(name, bot):
    data = await bot.data_fetcher.fetch_player_details()
    player = _find_demo(data, name)
    if not player:
        return _notfound(name, demos=True)
    kw = player.get("kill_weapons", {})
    vehicle_kills = _top_named(kw, weapon_vehicle_name, 10, exclude=lambda c: not is_vehicle_kill(c))
    veh_total = sum(c for w, c in kw.items() if is_vehicle_kill(w))
    empl_total = sum(c for w, c in kw.items() if weapon_vclass(w) == "emplacement")
    destroyed = player.get("total_vehicles_destroyed", 0)
    destroyed_by_type = _top_named(player.get("vehicles_destroyed_by_type", {}), clean_vehicle_name, 5)
    seat_kills = _top_named(player.get("seat_kills", {}), clean_seat, 6)
    embed = discord.Embed(title=f"🚁 Vehículos de {player['ign']}", color=discord.Color.dark_green())
    dval = f"**{destroyed}** vehículos enemigos destruidos"
    if destroyed_by_type:
        dval += "\n" + ", ".join(f"{_veh_emoji(v)}{v} ({c})" for v, c in destroyed_by_type)
    embed.add_field(name="🔥 Vehículos destruidos", value=dval, inline=False)
    file = None
    if vehicle_kills:
        top_line = ", ".join(f"{_veh_emoji(v)}**{v}** ({c})" for v, c in vehicle_kills[:3])
        extra = f"\n🎯 Con emplazamientos/estáticos: **{empl_total}**" if empl_total else ""
        embed.add_field(name=f"🎯 Kills con vehículos — {veh_total}",
                        value=f"Tripulando vehículos. Top: {top_line}{extra}", inline=False)
        buf = render_horizontal_bars([(v, c, "#00FFFF") for v, c in vehicle_kills],
                                     title=f"Kills con vehículos - {player['ign']}")
        file = discord.File(buf, filename="vehiculos.png")
        embed.set_image(url="attachment://vehiculos.png")
    elif empl_total:
        embed.add_field(name="🎯 Kills con emplazamientos",
                        value=f"**{empl_total}** kills con armas emplazadas/estáticas", inline=False)
    if seat_kills:
        embed.add_field(name="🪖 Kills por asiento",
                        value=", ".join(f"**{s}** ({c})" for s, c in seat_kills), inline=False)
    embed.set_footer(text=f"Datos de {player['rounds_played']} rondas | {standard_footer()}")
    return embed, file


async def build_kits(name, bot):
    data = await bot.data_fetcher.fetch_player_details()
    player = _find_demo(data, name)
    if not player:
        return _notfound(name, demos=True)
    kits = sorted(normalize_kits(player.get("kits_used", {})).items(),
                  key=lambda x: x[1], reverse=True)[:10]
    embed = discord.Embed(title=f"🎖️ Kits de {player['ign']}", color=discord.Color.blue())
    file = None
    if kits:
        total = sum(c for _, c in kits) or 1
        items = [(k, c / total * 100, "#00FFFF") for k, c in kits]
        buf = render_horizontal_bars(items, title=f"Top Kits - {player['ign']}",
                                     max_value=100, value_suffix="%")
        file = discord.File(buf, filename="kits.png")
        embed.set_image(url="attachment://kits.png")
        embed.description = f"Total de picks: **{sum(c for _, c in kits)}**"
    else:
        embed.description = "Sin datos de kits registrados."
    perf = player.get("kit_performance", {})
    ranked = sorted(((r, d.get("kills", 0), d.get("deaths", 0)) for r, d in perf.items()
                     if d.get("kills", 0) >= 10), key=lambda x: x[1] / max(x[2], 1), reverse=True)
    if ranked:
        lines = [f"{get_kit_emoji(r) or ''} **{r}** — K/D {k / max(dth, 1):.2f} ({k}/{dth})"
                 for r, k, dth in ranked[:8]]
        embed.add_field(name="⚔️ Desempeño por kit", value="\n".join(lines), inline=False)
    embed.set_footer(text=f"Datos de {player['rounds_played']} rondas | {standard_footer()}")
    return embed, file


async def build_assets(name, bot):
    data = await bot.data_fetcher.fetch_player_details()
    player = _find_demo(data, name)
    if not player:
        return _notfound(name, demos=True)
    kw = player.get("kill_weapons", {})
    CATS = [("infantry", "🔫", "A pie (infantería)"), ("ground", "🚛", "Vehículos terrestres"),
            ("air", "✈️", "Vehículos aéreos"), ("naval", "🚤", "Vehículos navales"),
            ("emplacement", "🎯", "Emplazamientos / estáticos"), ("env", "💥", "Entorno / desconocido")]
    totals: dict = {}
    tops: dict = {}
    for w, c in kw.items():
        cat = weapon_category(w)
        totals[cat] = totals.get(cat, 0) + c
        if cat in ("ground", "air", "naval", "emplacement"):
            nm = weapon_vehicle_name(w) or clean_weapon_name(w)
            d = tops.setdefault(cat, {})
            d[nm] = d.get(nm, 0) + c
    grand = sum(totals.values()) or 1
    embed = discord.Embed(title=f"🧩 Assets de {player['ign']}",
                          description=f"Cómo consigue sus **{grand}** kills, por tipo de medio",
                          color=discord.Color.teal())
    chart_items = []
    file = None
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
        embed.add_field(name=f"{emoji} {label}", value=f"**{tot}** kills · {pct:.0f}%{top_str}", inline=False)
        if cat != "env":
            chart_items.append((label, pct, "#00FFFF"))
    if chart_items:
        buf = render_horizontal_bars(chart_items, title=f"Kills por tipo de asset - {player['ign']}",
                                     max_value=100, value_suffix="%")
        file = discord.File(buf, filename="assets.png")
        embed.set_image(url="attachment://assets.png")
    embed.set_footer(text=f"Datos de {player['rounds_played']} rondas | {standard_footer()}")
    return embed, file


# tab_id -> (label, emoji, builder, needs_demos)
TABS = {
    "estadisticas": ("Estadísticas", "📊", build_estadisticas, False),
    "perfil": ("Perfil", "🎯", build_perfil, False),
    "historial": ("Historial", "📈", build_historial, False),
    "resumen": ("Resumen demos", "🧾", build_resumen, True),
    "vehiculos": ("Vehículos", "🚁", build_vehiculos, True),
    "kits": ("Kits", "🎖️", build_kits, True),
    "assets": ("Assets", "🧩", build_assets, True),
}


class _HubSelect(discord.ui.Select):
    def __init__(self, player_name: str, current: str, allow_demos: bool):
        self.player_name = player_name
        self.allow_demos = allow_demos
        options = [
            discord.SelectOption(label=label, value=tid, emoji=emoji, default=(tid == current))
            for tid, (label, emoji, _b, needs_demos) in TABS.items()
            if not (needs_demos and not allow_demos)
        ]
        super().__init__(placeholder="Cambiar vista…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        tid = self.values[0]
        label, _emoji, builder, _nd = TABS[tid]
        await interaction.response.defer()
        try:
            embed, file = await builder(self.player_name, interaction.client)
        except Exception as exc:
            logger.warning("Hub tab '%s' falló para %s: %s", tid, self.player_name, exc)
            embed, file = discord.Embed(description=f"No se pudo cargar **{label}**.",
                                        color=discord.Color.red()), None
        view = PlayerHubView(self.player_name, tid, self.allow_demos)
        await interaction.edit_original_response(
            embed=embed, view=view, attachments=[file] if file else [])


class PlayerHubView(discord.ui.View):
    """Select de tabs + botones de acción (comparar / rondas / glosario)."""

    def __init__(self, player_name: str, current: str, allow_demos: bool = True, *, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.add_item(_HubSelect(player_name, current, allow_demos))
        from bot.ui.player_card_actions import PlayerCardActionButton
        acts = ("cmp", "rounds", "glos") if allow_demos else ("cmp", "glos")
        for act in acts:
            self.add_item(PlayerCardActionButton(act, player_name))
