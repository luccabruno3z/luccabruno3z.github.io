"""Perfil de jugador unificado (Components V2) — reemplaza la PlayerCard de -estadisticas
y el hub de embeds de -perfil / comandos de demos.

Una sola tarjeta con encabezado fijo (jugador, tier, clan) y pestañas:
Resumen · Récords · Perfil · Historial, más un menú con las vistas de demos
(Resumen demos, Kits, Vehículos, Assets). Cambiar de pestaña edita el mismo mensaje.

- Las barras son de emojis coloreados por tier (bot.ui.theme.meter), en todas las pestañas.
- Botones y menú son DynamicItems: siguen andando tras un redeploy. El custom_id lleva
  el id de quien abrió la tarjeta; si otro toca, recibe su propia copia efímera.
- Las vistas de demos reusan los builders de player_hub (embed + gráfico) y se pasan a
  componentes V2 con ``embed_to_items``, así todo se ve con el mismo formato.
"""

from __future__ import annotations

import logging
import re

import discord

from bot.config import BASE_URL, clan_logo_url
from bot.ui.theme import meter, legend, tier_color, player_records, last_seen, ACCENT
from bot.utils import (
    find_player, standard_footer, format_number, get_player_archetype,
    get_player_archetype_desc, get_player_radar, get_player_ratings, tier_emoji, _tier_name,
    stat_confidence_warning, sigmoid_penalty_display,
)

logger = logging.getLogger(__name__)

# tab_id -> (label, necesita demos). Orden = orden de los botones.
MAIN_TABS = {
    "resumen": ("Resumen", False),
    "records": ("Récords", True),
    "perfil": ("Perfil", False),
    "historial": ("Historial", False),
}
# Vistas de demos (menú desplegable) -> (label, builder en player_hub)
DEMO_TABS = {
    "demos": "Resumen demos",
    "kits": "Kits",
    "vehiculos": "Vehículos",
    "assets": "Assets",
}
ALL_TABS = set(MAIN_TABS) | set(DEMO_TABS)

_RADAR_LABELS = [
    ("letalidad", "Letalidad"), ("supervivencia", "Supervivencia"), ("teamwork", "Teamwork"),
    ("impacto", "Impacto"), ("consistencia", "Consistencia"), ("versatilidad", "Versatilidad"),
]


def _f2(v) -> str:
    return f"{(v or 0):.2f}".replace(".", ",")


def _top_pct(value: float, values: list[float]) -> tuple[float, str]:
    """(fracción 0-1 de jugadores por debajo, 'top N%')."""
    if not values:
        return 0.0, ""
    below = sum(1 for v in values if v <= value) / len(values)
    return below, f"top {max(1, round((1 - below) * 100))}%"


def _metric_line(bar: str, label: str, value: str, extra: str = "") -> str:
    return f"{bar} **{label}** `{value}`" + (f" · {extra}" if extra else "")


# ── Embed clásico → componentes V2 (para las vistas de demos e historial) ─────
def embed_to_items(embed: discord.Embed) -> list[discord.ui.Item]:
    items: list[discord.ui.Item] = []
    head = []
    if embed.title:
        head.append(f"### {embed.title}")
    if embed.description:
        head.append(embed.description)
    if head:
        items.append(discord.ui.TextDisplay("\n".join(head)))
    fields = [f for f in embed.fields if (f.value or "").strip() and f.value != "​"]
    if fields:
        txt = "\n\n".join(
            (f"**{f.name}**\n{f.value}" if f.name and f.name.strip("​ ") else f.value)
            for f in fields
        )
        items.append(discord.ui.TextDisplay(txt[:3000]))
    url = embed.image.url if embed.image else None
    if url:
        items.append(discord.ui.MediaGallery(discord.MediaGalleryItem(url)))
    if embed.footer and embed.footer.text:
        items.append(discord.ui.TextDisplay(f"-# {embed.footer.text}"))
    return items


# ── Contexto de un jugador (una sola carga por render) ────────────────────────
async def load_context(bot, name: str) -> dict | None:
    fetcher = bot.data_fetcher
    data = await fetcher.fetch_all_players()
    ordered = sorted(data, key=lambda x: x.get("Performance Score", 0), reverse=True)
    p = find_player(ordered, name)
    if not p:
        return None
    pl = p["Player"]
    low = pl.lower()
    clan = p.get("Clan", "—")
    rk_global = next((i + 1 for i, e in enumerate(ordered) if e.get("Player", "").lower() == low), None)
    clan_list = [e for e in ordered if e.get("Clan") == clan]
    rk_clan = next((i + 1 for i, e in enumerate(clan_list) if e.get("Player", "").lower() == low), None)
    try:
        tc = await fetcher.fetch_tier_config()
        thr = tc.get("thresholds") if isinstance(tc, dict) else None
    except Exception:
        thr = None
    try:
        demo = await fetcher.fetch_player_details()
        dp = find_player(demo, pl, key="ign") if demo else None
    except Exception:
        dp = None
    trend = ""
    try:
        safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", pl)
        hist = await fetcher.fetch_json(f"{BASE_URL}/graphs/history/{safe}_history.json", use_stale_on_error=False)
        if isinstance(hist, list) and len(hist) >= 2:
            a, b = hist[-2].get("Performance Score", 0), hist[-1].get("Performance Score", 0)
            trend = " 📈" if b > a else (" 📉" if b < a else "")
    except Exception:
        pass
    return {"p": p, "all": data, "clan_list": clan_list, "rk_global": rk_global, "rk_clan": rk_clan,
            "thr": thr, "dp": dp, "trend": trend}


# ── Contenido de cada pestaña: (items, files) ────────────────────────────────
def _tab_resumen(ctx: dict):
    p, thr, data = ctx["p"], ctx["thr"], ctx["all"]
    ps = p.get("Performance Score", 0) or 0
    kd = p.get("K/D Ratio", 0) or 0
    kpr = p.get("Kills per Round", 0) or 0
    kd_f, kd_top = _top_pct(kd, [q.get("K/D Ratio", 0) or 0 for q in data])
    kpr_f, kpr_top = _top_pct(kpr, [q.get("Kills per Round", 0) or 0 for q in data])
    _ps_f, ps_top = _top_pct(ps, [q.get("Performance Score", 0) or 0 for q in data])
    rounds = p.get("Rounds", 0) or 0

    lines = [
        "### Resumen",
        _metric_line(meter(ps, thr), "Performance", _f2(ps) + ctx["trend"], ps_top),
        _metric_line(meter(kd_f, thr), "K/D", _f2(kd), kd_top),
        _metric_line(meter(kpr_f, thr), "KPR", _f2(kpr), kpr_top),
        f"-# Kills {format_number(p.get('Total Kills', 0))} · Muertes {format_number(p.get('Total Deaths', 0))}"
        f" · Score/ronda {p.get('Score per Round', 0):.0f} · Rondas {format_number(rounds)}",
    ]
    bd = [
        ("Combate (K/D)", p.get("Normalized_KD", 0)), ("Puntuación (SPR)", p.get("Normalized_Score", 0)),
        ("Agresividad (KPR)", p.get("Normalized_Kills_Per_Round", 0)), ("Experiencia", p.get("Normalized_Rounds", 0)),
    ]
    blines = ["### Desglose del puntaje"]
    blines += [_metric_line(meter(v or 0, thr), lbl, f"{(v or 0) * 100:.0f}") for lbl, v in bd]
    ratings = get_player_ratings(p)
    if ratings:
        blines.append("-# Índices: " + " · ".join(
            f"{lbl} {ratings.get(k, 0):.0f}" for k, lbl in
            (("combat", "Combate"), ("tactical", "Táctico"), ("reliability", "Fiabilidad"), ("impact", "Impacto"))))

    extra = []
    t = thr or {}
    for key, nm in (("soldado", "Soldado"), ("experimentado", "Experimentado"), ("veterano", "Veterano"), ("elite", "Élite")):
        if t.get(key) and ps < t[key]:
            extra.append(f"Próximo tier: **{nm}** — te faltan **{_f2(t[key] - ps)}** pts")
            break
    if rounds < 50:
        extra.append(f"-# Con {rounds} rondas tus stats aún no son representativos (50 para aparecer en `-top`).")
    else:
        for w in (stat_confidence_warning(rounds), sigmoid_penalty_display(rounds)):
            if w:
                extra.append(f"-# {w.strip()}")
    best = (player_records(ctx["dp"]) or {}).get("best")
    if best:
        extra.append(f"Mejor ronda: **{best['kills']} kills** en **{best['where'].split(' · ')[0]}** — más en **Récords**")

    items = [discord.ui.TextDisplay("\n".join(lines)), discord.ui.Separator(),
             discord.ui.TextDisplay("\n".join(blines))]
    if extra:
        items += [discord.ui.Separator(), discord.ui.TextDisplay("\n".join(extra))]
    return items, []


def _tab_records(ctx: dict):
    rec = player_records(ctx["dp"])
    if not rec:
        return [discord.ui.TextDisplay("### Récords\nTodavía no hay rondas con demo para este jugador.")], []
    out = ["### Récords"]
    if rec["best"]:
        b = rec["best"]
        out.append(f"**Mejor ronda** — **{b['kills']}** kills · **{b['deaths']}** muertes · **{b['score']}** pts")
        out.append(f"-# {b['where']}")
    items = [discord.ui.TextDisplay("\n".join(out))]
    if rec["items"]:
        pairs = [rec["items"][i:i + 2] for i in range(0, len(rec["items"]), 2)]
        items.append(discord.ui.TextDisplay("\n".join(
            " · ".join(f"{lbl} **{val}**" for lbl, val in pair) for pair in pairs)))
    if rec["bars"]:
        items.append(discord.ui.TextDisplay("\n".join(
            _metric_line(meter(frac, ctx["thr"]), lbl, shown) for lbl, frac, shown in rec["bars"])))
    items.append(discord.ui.TextDisplay(f"-# De {rec['rounds']} rondas con demo"))
    return items, []


def _tab_perfil(ctx: dict):
    from bot.services.chart_renderer import render_radar_chart
    p, thr, data = ctx["p"], ctx["thr"], ctx["all"]
    radar = get_player_radar(p)
    if not radar:
        return [discord.ui.TextDisplay("### Perfil de habilidades\nRadar no disponible todavía (faltan datos).")], []
    clan = p.get("Clan", "")
    mates = [q for q in data if q.get("Clan") == clan and q.get("radar")]
    avg = {k: (sum(q["radar"].get(k, 0) for q in mates) / len(mates) if mates else 0) for k, _ in _RADAR_LABELS}
    lines = ["### Perfil de habilidades"]
    for k, lbl in _RADAR_LABELS:
        v = radar.get(k, 0) or 0
        diff = v - avg[k]
        cmp = f"{'+' if diff >= 0 else '−'}{abs(diff) * 100:.0f} vs {clan}" if mates else ""
        lines.append(_metric_line(meter(v, thr), lbl, f"{v * 100:.0f}", cmp))
    desc = get_player_archetype_desc(p)
    if desc:
        lines.append(f"-# {desc}")
    buf = render_radar_chart({lbl: radar.get(k, 0) for k, lbl in _RADAR_LABELS},
                             {lbl: avg[k] for k, lbl in _RADAR_LABELS}, p["Player"], clan)
    f = discord.File(buf, filename="radar.png")
    return [discord.ui.TextDisplay("\n".join(lines)),
            discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://radar.png"))], [f]


async def _tab_from_embed(builder, name: str, bot):
    embed, file = await builder(name, bot)
    return embed_to_items(embed), [file] if file else []


async def build_tab(ctx: dict, tab: str, bot):
    from bot.ui import player_hub as hub
    name = ctx["p"]["Player"]
    if tab == "records":
        return _tab_records(ctx)
    if tab == "perfil":
        return _tab_perfil(ctx)
    if tab == "historial":
        return await _tab_from_embed(hub.build_historial, name, bot)
    if tab == "demos":
        return await _tab_from_embed(hub.build_resumen, name, bot)
    if tab in ("kits", "vehiculos", "assets"):
        return await _tab_from_embed(getattr(hub, f"build_{tab}"), name, bot)
    return _tab_resumen(ctx)


# ── Interacción: botones de pestaña + menú de demos (persistentes) ────────────
def _cid(kind: str, tab: str, owner: int, name: str) -> str:
    return f"pp:{kind}:{tab}:{owner}:{name}"[:100]


class ProfileTabButton(discord.ui.DynamicItem[discord.ui.Button],
                       template=r"pp:t:(?P<tab>[a-z]+):(?P<owner>\d+):(?P<name>.+)"):
    def __init__(self, tab: str, owner: int, name: str, *, active: bool = False):
        self.tab, self.owner, self.name = tab, owner, name
        super().__init__(discord.ui.Button(
            label=MAIN_TABS.get(tab, (tab,))[0],
            style=discord.ButtonStyle.primary if active else discord.ButtonStyle.secondary,
            custom_id=_cid("t", tab, owner, name),
        ))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["tab"], int(match["owner"]), match["name"])

    async def callback(self, interaction: discord.Interaction):
        await switch_tab(interaction, self.name, self.tab, self.owner)


class ProfileDemoSelect(discord.ui.DynamicItem[discord.ui.Select],
                        template=r"pp:s:(?P<tab>[a-z]+):(?P<owner>\d+):(?P<name>.+)"):
    def __init__(self, tab: str, owner: int, name: str):
        self.owner, self.name = owner, name
        super().__init__(discord.ui.Select(
            placeholder="Vistas de demos: Kits, Vehículos, Assets…",
            custom_id=_cid("s", tab, owner, name),
            options=[discord.SelectOption(label=lbl, value=tid, default=(tid == tab))
                     for tid, lbl in DEMO_TABS.items()],
        ))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["tab"], int(match["owner"]), match["name"])

    async def callback(self, interaction: discord.Interaction):
        await switch_tab(interaction, self.name, self.item.values[0], self.owner)


def _allow_demos(bot, guild_id) -> bool:
    gs = getattr(bot, "guild_settings", None)
    mode = gs.get_mode(guild_id) if (gs and guild_id) else "combined"
    return mode in ("combined", "demos")


class PlayerProfileView(discord.ui.LayoutView):
    """La tarjeta completa para un jugador y una pestaña ya renderizada."""

    def __init__(self, ctx: dict, tab: str, items: list[discord.ui.Item], *, owner: int, allow_demos: bool):
        super().__init__(timeout=None)
        from bot.ui.player_card_actions import PlayerCardActionButton
        p, thr = ctx["p"], ctx["thr"]
        name, clan = p["Player"], p.get("Clan", "—")
        ps = p.get("Performance Score", 0) or 0
        se, sn = get_player_archetype(p)
        rk = f"Ranking global **#{ctx['rk_global']}**" if ctx["rk_global"] else ""
        if ctx["rk_clan"]:
            rk += f" · clan **#{ctx['rk_clan']}**"
        header = discord.ui.Section(
            f"## {name}  ·  `{clan}`",
            f"{tier_emoji(ps, thr)} **{_tier_name(ps, thr)}** · {se} {sn}",
            f"-# {rk}" if rk else "-# —",
            accessory=discord.ui.Thumbnail(clan_logo_url(clan)),
        )
        tabs = [ProfileTabButton(t, owner, name, active=(t == tab))
                for t, (_lbl, needs) in MAIN_TABS.items() if allow_demos or not needs]
        children: list[discord.ui.Item] = [header, discord.ui.ActionRow(*tabs)]
        if allow_demos and ctx["dp"]:
            children.append(discord.ui.ActionRow(ProfileDemoSelect(tab if tab in DEMO_TABS else "x", owner, name)))
        children.append(discord.ui.Separator())
        children += items
        children.append(discord.ui.Separator())
        # Actividad real = fecha de la última ronda con demo. El "Activity Index" del
        # scraper mide volumen/rendimiento (no mira fechas): se muestra como
        # "Participación" para no confundirlo con estar activo.
        info = [last_seen(ctx["dp"])]
        ai = p.get("Activity Index")
        if ai is not None:
            info.append(f"Participación {ai:.0f}/100")
        # standard_footer da la hora de la última actualización de los DATOS, no del jugador.
        updated = standard_footer(p).replace("📅 ", "")
        children.append(discord.ui.TextDisplay(
            " · ".join(info) + f"\n-# {legend(thr)}\n-# Datos actualizados {updated}"))
        acts = ("cmp", "rounds", "glos") if (allow_demos and ctx["dp"]) else ("cmp", "glos")
        children.append(discord.ui.ActionRow(*[PlayerCardActionButton(a, name) for a in acts]))
        self.add_item(discord.ui.Container(*children, accent_colour=tier_color(ps, thr) or ACCENT))


async def render_profile(bot, name: str, tab: str, *, owner: int, guild_id):
    """→ (view, files) o (None, mensaje de error)."""
    ctx = await load_context(bot, name)
    if not ctx:
        return None, f"⚠️ Jugador '{name}' no encontrado. Probá `-buscar <nombre>` para verificar."
    allow = _allow_demos(bot, guild_id)
    if tab not in ALL_TABS or (not allow and (tab in DEMO_TABS or MAIN_TABS.get(tab, ("", False))[1])):
        tab = "resumen"
    try:
        items, files = await build_tab(ctx, tab, bot)
    except Exception as exc:
        logger.warning("Pestaña '%s' falló para %s: %s", tab, name, exc)
        items, files = [discord.ui.TextDisplay("No se pudo cargar esta vista.")], []
    return PlayerProfileView(ctx, tab, items, owner=owner, allow_demos=allow), files


async def send_profile(ctx, name: str, tab: str = "resumen"):
    """Para los comandos: manda la tarjeta en la pestaña pedida."""
    view, files = await render_profile(ctx.bot, name, tab, owner=ctx.author.id,
                                       guild_id=ctx.guild.id if ctx.guild else None)
    if view is None:
        await ctx.send(files)
        return
    await ctx.send(view=view, files=files)


async def switch_tab(interaction: discord.Interaction, name: str, tab: str, owner: int):
    mine = interaction.user.id == owner
    await interaction.response.defer(ephemeral=not mine, thinking=not mine)
    view, files = await render_profile(interaction.client, name, tab, owner=interaction.user.id,
                                       guild_id=interaction.guild_id)
    if view is None:
        await interaction.followup.send(files, ephemeral=True)
        return
    if mine:
        await interaction.edit_original_response(view=view, attachments=files)
    else:
        await interaction.followup.send(view=view, files=files, ephemeral=True)
