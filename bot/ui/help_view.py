"""Dynamic, always-complete help (Components V2).

Builds the command list from the bot's registered commands, grouped by cog, so
every command — including reversioned/new ones — appears automatically. A Select
switches category; a note points to `/glosario`.
"""

from __future__ import annotations

import discord

# cog class name -> (emoji + friendly label). Unmapped cogs fall in "Otros".
_COG_LABELS = {
    "Stats": "📊 Estadísticas",
    "DetailedStats": "🎮 Demos / detalle",
    "Compare": "⚔️ Comparar / equipos",
    "Charts": "📈 Gráficos",
    "Tips": "💡 Tips",
    "Polls": "🗳️ Encuestas",
    "Countdown": "⏳ Countdown",
    "Roles": "🔧 Roles (admin)",
    "Automation": "⚙️ Automatización (admin)",
    "Misc": "ℹ️ General",
    "Suggestions": "ℹ️ General",
}
# internos / owner-only / el help mismo (no se muestran)
_HIDDEN = {"apagar", "setup_emojis", "help_redirect", "ayuda", "expsug"}
# Comandos que viven en otro cog pero conceptualmente van en otra categoría del help.
_CMD_CATEGORY = {"perfil": "📈 Gráficos"}  # el radar es un gráfico, aunque esté en Stats
# Descripción de respaldo para los comandos sin docstring ni description= en el decorador.
_DESCRIPTIONS = {
    "estadisticas": "Estadísticas completas de un jugador (tarjeta).",
    "top": "Ranking de jugadores por categoría y métrica.",
    "buscar_usuario": "Busca un jugador por nombre (coincidencia parcial).",
    "promedios": "Promedios de estadísticas de un clan.",
    "promedios_tops": "Top de clanes por promedio de una métrica.",
    "analizar_equipo": "Analiza la composición y el balance de un equipo.",
    "comparar_equipos": "Compara dos equipos lado a lado.",
    "sugerir_equipo": "Sugiere una alineación para un clan.",
    "guias": "Links a las guías de la página.",
    "pagina": "Link a la página de estadísticas.",
    "visualizador": "Link al visualizador 2D de partidas.",
    "hola": "Saludo rápido del bot.",
}
_ACCENT = 0x00FFFF


def build_help_categories(bot) -> dict[str, list[tuple[str, str]]]:
    """Return {category_label: [(invocation, short_desc), ...]} from live commands."""
    cats: dict[str, list[tuple[str, str]]] = {}
    graph_shortcuts = 0
    for cmd in sorted(bot.commands, key=lambda c: c.qualified_name):
        if cmd.hidden or cmd.name in _HIDDEN:
            continue
        # Collapse the 21 per-clan graph shortcuts (-graficoldh, -graficosae...)
        # into a single line instead of flooding the category.
        if cmd.name.startswith("grafico") and cmd.name != "grafico":
            graph_shortcuts += 1
            continue
        label = _CMD_CATEGORY.get(cmd.name) or _COG_LABELS.get(cmd.cog_name or "", "🧩 Otros")
        invocation = f"**`-{cmd.name}`**"
        if cmd.aliases:
            invocation += " " + " ".join(f"`-{a}`" for a in cmd.aliases[:3])
        desc = (cmd.description or cmd.help or "").strip().split("\n")[0]
        if not desc:
            desc = _DESCRIPTIONS.get(cmd.name, "")
        cats.setdefault(label, []).append((invocation, desc))
    if graph_shortcuts:
        cats.setdefault("📈 Gráficos", []).append(
            ("`-grafico<clan>`", f"Atajos por clan ({graph_shortcuts}): `-graficoldh`, `-graficosae`, …")
        )
    return cats


class _HelpSelect(discord.ui.Select):
    def __init__(self, categories: list[str], current: str):
        super().__init__(
            placeholder="Elegí una categoría de comandos",
            min_values=1, max_values=1,
            options=[discord.SelectOption(label=c, value=c, default=(c == current))
                     for c in categories[:25]],
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.show(interaction, self.values[0])


class HelpView(discord.ui.LayoutView):
    def __init__(self, bot, category: str | None = None):
        super().__init__(timeout=300)
        self.cats = build_help_categories(bot)
        # Stable, sensible order: known labels first, then the rest.
        known = [v for v in _COG_LABELS.values() if v in self.cats]
        rest = [c for c in self.cats if c not in known]
        self.order = known + rest
        self.category = category if category in self.cats else (self.order[0] if self.order else "")
        self._render()

    def _render(self):
        self.clear_items()
        entries = self.cats.get(self.category, [])
        # Cada comando en su bloque: nombre en negrita, descripción como subtexto
        # atenuado debajo, y una línea en blanco entre comandos (legibilidad).
        n = len(entries)
        lines = [f"## {self.category}", f"-# {n} comando{'s' if n != 1 else ''}", ""]
        for inv, desc in entries:
            lines.append(inv)
            if desc:
                lines.append(f"-# {desc}")
            lines.append("")
        block = "\n".join(lines)[:3950]

        container = discord.ui.Container(
            discord.ui.TextDisplay(block),
            discord.ui.Separator(),
            discord.ui.ActionRow(_HelpSelect(self.order, self.category)),
            discord.ui.TextDisplay(
                "-# Elegí otra categoría ↑ · ¿dudás de un término? `/glosario` o el botón 📖"
            ),
            accent_colour=_ACCENT,
        )
        self.add_item(container)

    async def show(self, interaction: discord.Interaction, category: str):
        self.category = category
        self._render()
        await interaction.response.edit_message(view=self)
