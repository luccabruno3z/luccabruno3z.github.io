"""-menu: un único mensaje navegable (Components V2) que junta las secciones del bot,
con la misma estructura que las pestañas de la web: Mi perfil · Buscar · Rankings ·
Clanes · Partidas · Equipos · Ayuda.

- Cada botón re-arma la tarjeta y EDITA el mismo mensaje (con "← Menú" para volver).
- Solo navega quien lo abrió (su id va en el custom_id); otro usuario recibe un aviso.
- Botones = DynamicItems: siguen funcionando después de un redeploy.
- "Mi perfil" usa el jugador vinculado con -vincular (bot.services.links).
"""

from __future__ import annotations

import logging

import discord

from bot.config import BOT_THUMBNAIL, MIN_ROUNDS
from bot.services import links
from bot.ui.theme import ACCENT, meter, accent_meter, LIST_SEGMENTS, tier_color
from bot.utils import find_player, format_number, rank_medal, tier_emoji, _tier_name

logger = logging.getLogger(__name__)

SCREENS = ("home", "perfil", "rankings", "clanes", "partidas", "equipos")
_WEB = "https://luccabruno3z.github.io/#/"


def _f2(v) -> str:
    return f"{(v or 0):.2f}".replace(".", ",")


async def _thresholds(fetcher):
    try:
        tc = await fetcher.fetch_tier_config()
        return tc.get("thresholds") if isinstance(tc, dict) else None
    except Exception:
        return None


class MenuButton(discord.ui.DynamicItem[discord.ui.Button],
                 template=r"mn:(?P<action>[a-z]+):(?P<owner>\d+)"):
    """Botón de navegación del menú. action = una pantalla, 'search', 'help' o 'open'."""

    def __init__(self, action: str, owner: int, label: str, *,
                 style: discord.ButtonStyle = discord.ButtonStyle.secondary):
        self.action, self.owner = action, owner
        super().__init__(discord.ui.Button(label=label, style=style, custom_id=f"mn:{action}:{owner}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["action"], int(match["owner"]), item.label or "")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner:
            return True
        await interaction.response.send_message(
            "Este menú es de otra persona. Abrí el tuyo con `-menu`.", ephemeral=True)
        return False

    async def callback(self, interaction: discord.Interaction):
        bot = interaction.client
        if self.action == "search":
            await interaction.response.send_modal(SearchModal())
            return
        if self.action == "help":
            from bot.ui.help_view import HelpView
            await interaction.response.send_message(view=HelpView(bot), ephemeral=True)
            return
        if self.action == "open":
            ign = links.get(self.owner)
            if not ign:
                await interaction.response.send_message("Primero vinculá tu jugador con `-vincular <ign>`.",
                                                        ephemeral=True)
                return
            from bot.ui.player_profile import render_profile
            await interaction.response.defer(thinking=True)
            view, files = await render_profile(bot, ign, "resumen", owner=self.owner,
                                               guild_id=interaction.guild_id)
            if view is None:
                await interaction.followup.send(files, ephemeral=True)
            else:
                await interaction.followup.send(view=view, files=files)
            return
        await interaction.response.defer()
        view = await build_menu(bot, self.action, self.owner)
        await interaction.edit_original_response(view=view, attachments=[])


class SearchModal(discord.ui.Modal, title="Buscar jugador"):
    nombre = discord.ui.TextInput(label="Nombre del jugador", placeholder="Ej: W4RR10R", max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        from bot.ui.player_profile import render_profile
        await interaction.response.defer(thinking=True)
        view, files = await render_profile(interaction.client, self.nombre.value.strip(), "resumen",
                                           owner=interaction.user.id, guild_id=interaction.guild_id)
        if view is None:
            await interaction.followup.send(files, ephemeral=True)
        else:
            await interaction.followup.send(view=view, files=files)


def _back(owner: int) -> MenuButton:
    return MenuButton("home", owner, "← Menú")


# ── Pantallas: cada una devuelve (accent, [items]) ────────────────────────────
async def _home(bot, owner: int):
    ign = links.get(owner)
    you = "Vinculá tu jugador con `-vincular <ign>` para verlo acá."
    accent = ACCENT
    if ign:
        try:
            data = await bot.data_fetcher.fetch_all_players()
            thr = await _thresholds(bot.data_fetcher)
            ordered = sorted(data, key=lambda x: x.get("Performance Score", 0), reverse=True)
            p = find_player(ordered, ign)
        except Exception:
            p, thr, ordered = None, None, []
        if p:
            ps = p.get("Performance Score", 0) or 0
            rk = next((i + 1 for i, e in enumerate(ordered) if e.get("Player") == p.get("Player")), None)
            you = (f"**Tu jugador:** {p['Player']} · {tier_emoji(ps, thr)} **{_tier_name(ps, thr)}**"
                   f" · Performance `{_f2(ps)}`" + (f" · `#{rk}` global" if rk else ""))
        else:
            you = f"**Tu jugador:** {ign} (todavía sin datos de PRStats)"
    head = discord.ui.Section(
        "## Legión de Hierro · Menú",
        "Estadísticas de Project Reality para LDH y los clanes LATAM.",
        "-# Elegí una sección: cada botón actualiza este mismo mensaje.",
        accessory=discord.ui.Thumbnail(BOT_THUMBNAIL),
    )
    rows = [
        discord.ui.ActionRow(
            MenuButton("perfil", owner, "Mi perfil", style=discord.ButtonStyle.primary),
            MenuButton("search", owner, "Buscar jugador"),
            MenuButton("rankings", owner, "Rankings"),
        ),
        discord.ui.ActionRow(
            MenuButton("clanes", owner, "Clanes"),
            MenuButton("partidas", owner, "Partidas"),
            MenuButton("equipos", owner, "Equipos"),
            MenuButton("help", owner, "Ayuda"),
        ),
    ]
    sub = "-# Vinculado con -vincular · cambialo cuando quieras" if ign else "-# Ej: `-vincular W4RR10R`"
    return accent, [head, discord.ui.Separator(), discord.ui.TextDisplay(f"{you}\n{sub}"),
                    discord.ui.Separator(), discord.ui.TextDisplay("### ¿Qué querés ver?"), *rows]


async def _perfil(bot, owner: int):
    ign = links.get(owner)
    if not ign:
        return ACCENT, [discord.ui.TextDisplay(
            "-# Menú › Mi perfil\n## Mi perfil\nTodavía no vinculaste tu jugador.\n"
            "Usá `-vincular <ign>` (por ejemplo `-vincular W4RR10R`) y volvé acá."),
            discord.ui.ActionRow(_back(owner), MenuButton("search", owner, "Buscar jugador"))]
    from bot.ui.player_profile import load_context
    from bot.ui.theme import player_records
    ctx = await load_context(bot, ign)
    if not ctx:
        return ACCENT, [discord.ui.TextDisplay(f"-# Menú › Mi perfil\nNo encontré a **{ign}** en PRStats."),
                        discord.ui.ActionRow(_back(owner))]
    p, thr = ctx["p"], ctx["thr"]
    ps = p.get("Performance Score", 0) or 0
    lines = [
        "-# Menú › Mi perfil",
        f"## {p['Player']} · `{p.get('Clan', '—')}`",
        f"{tier_emoji(ps, thr)} **{_tier_name(ps, thr)}**" + (f" · `#{ctx['rk_global']}` global" if ctx["rk_global"] else ""),
        f"{meter(ps, thr)} **Performance** `{_f2(ps)}`",
        f"K/D `{_f2(p.get('K/D Ratio'))}` · KPR `{_f2(p.get('Kills per Round'))}` · Rondas `{format_number(p.get('Rounds', 0))}`",
    ]
    from bot.ui.theme import last_seen
    lines.append(last_seen(ctx["dp"]))
    best = (player_records(ctx["dp"]) or {}).get("best")
    if best:
        lines.append(f"Mejor ronda: **{best['kills']} kills** en **{best['where'].split(' · ')[0]}**")
    return tier_color(ps, thr), [
        discord.ui.TextDisplay("\n".join(lines)),
        discord.ui.ActionRow(MenuButton("open", owner, "Abrir perfil completo", style=discord.ButtonStyle.primary),
                             _back(owner)),
    ]


async def _rankings(bot, owner: int):
    data = await bot.data_fetcher.fetch_all_players()
    thr = await _thresholds(bot.data_fetcher)
    ranked = sorted((p for p in data if p.get("Rounds", 0) >= MIN_ROUNDS),
                    key=lambda x: x.get("Performance Score", 0), reverse=True)[:10]
    lines = ["-# Menú › Rankings", "## Top · Performance Score"]
    for i, p in enumerate(ranked, 1):
        ps = p.get("Performance Score", 0) or 0
        lead = rank_medal(i) if i <= 3 else meter(ps, thr, length=LIST_SEGMENTS)
        lines.append(f"{lead} `{i:>2}.` **{p.get('Player')}** · {p.get('Clan', '')} · `{_f2(ps)}`")
    lines.append(f"-# Mínimo {MIN_ROUNDS} rondas · el ranking completo con filtros: `-top`")
    return 0xFFD700, [discord.ui.TextDisplay("\n".join(lines)), discord.ui.ActionRow(
        _back(owner),
        discord.ui.Button(label="Ver en la web", style=discord.ButtonStyle.link, url=_WEB + "rankings"))]


async def _clanes(bot, owner: int):
    data = await bot.data_fetcher.fetch_clan_averages()
    ranked = sorted(data or [], key=lambda c: c.get("Performance Score", 0), reverse=True)[:10]
    top = (ranked[0].get("Performance Score", 0) or 0) if ranked else 0
    lines = ["-# Menú › Clanes", "## Clanes · promedio de Performance"]
    for i, c in enumerate(ranked, 1):
        ps = c.get("Performance Score", 0) or 0
        lead = rank_medal(i) if i <= 3 else accent_meter(ps / top if top else 0, LIST_SEGMENTS)
        lines.append(f"{lead} `{i:>2}.` **{c.get('Clan')}** · K/D `{_f2(c.get('K/D Ratio'))}` · `{_f2(ps)}`")
    lines.append("-# Detalle por clan: `-promedios <clan>` · comparar: `-compare <clan1> <clan2>`")
    return 0xFFA500, [discord.ui.TextDisplay("\n".join(lines)), discord.ui.ActionRow(
        _back(owner),
        discord.ui.Button(label="Ver en la web", style=discord.ButtonStyle.link, url=_WEB + "clanes"))]


async def _partidas(bot, owner: int):
    try:
        lb = await bot.data_fetcher.fetch_leaderboard("semana")
    except Exception:
        lb = None
    players = (lb or {}).get("players", []) if isinstance(lb, dict) else []
    ranked = sorted(players, key=lambda p: p.get("kills", 0), reverse=True)[:8]
    top = (ranked[0].get("kills", 0) or 0) if ranked else 0
    lines = ["-# Menú › Partidas", "## Más kills · última semana"]
    if isinstance(lb, dict):
        lines.append(f"-# {format_number(lb.get('total_rounds', 0))} rondas con demo en 7 días")
    for i, p in enumerate(ranked, 1):
        lead = rank_medal(i) if i <= 3 else accent_meter(p.get("kills", 0) / top if top else 0, LIST_SEGMENTS)
        lines.append(f"{lead} `{i:>2}.` **{p.get('ign')}** · `{p.get('kills', 0)}` · {p.get('rounds', 0)} rondas")
    if not ranked:
        lines.append("Todavía no hay rondas esta semana.")
    lines.append("-# Otros períodos y métricas: `-top_periodo` · mapas: `-mapa <nombre>`")
    return 0xFFD700, [discord.ui.TextDisplay("\n".join(lines)), discord.ui.ActionRow(
        _back(owner),
        discord.ui.Button(label="Ver en la web", style=discord.ButtonStyle.link, url=_WEB + "partidas"))]


async def _equipos(bot, owner: int):
    text = (
        "-# Menú › Equipos\n## Equipos\n"
        "**Predecir una partida** — `-prediccion` con los jugadores de cada equipo.\n"
        "**Analizar un equipo** — `-analizar_equipo jugador1 jugador2 …`\n"
        "**Comparar equipos** — `-comparar_equipos`\n"
        "**Comparar dos jugadores o clanes** — `-compare A B`\n"
        "-# En la web hay un predictor con autocompletado"
    )
    return ACCENT, [discord.ui.TextDisplay(text), discord.ui.ActionRow(
        _back(owner),
        discord.ui.Button(label="Abrir en la web", style=discord.ButtonStyle.link, url=_WEB + "equipos"))]


_BUILDERS = {"home": _home, "perfil": _perfil, "rankings": _rankings, "clanes": _clanes,
             "partidas": _partidas, "equipos": _equipos}


async def build_menu(bot, screen: str, owner: int) -> discord.ui.LayoutView:
    builder = _BUILDERS.get(screen, _home)
    try:
        accent, items = await builder(bot, owner)
    except Exception as exc:
        logger.warning("Pantalla '%s' del menú falló: %s", screen, exc)
        accent, items = ACCENT, [discord.ui.TextDisplay("No se pudo cargar esta sección. Probá de nuevo."),
                                 discord.ui.ActionRow(_back(owner))]
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(discord.ui.Container(*items, accent_colour=accent))
    return view
