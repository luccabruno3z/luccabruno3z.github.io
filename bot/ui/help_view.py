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
}
_HIDDEN = {"apagar", "setup_emojis", "help_redirect", "ayuda"}  # internos / el help mismo
# Comandos que viven en otro cog pero conceptualmente van en otra categoría del help.
_CMD_CATEGORY = {"perfil": "📈 Gráficos"}  # el radar es un gráfico, aunque esté en Stats
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
        invocation = f"`-{cmd.name}`"
        if cmd.aliases:
            invocation += "  " + " ".join(f"`-{a}`" for a in cmd.aliases[:3])
        desc = (cmd.help or "").strip().split("\n")[0] or "—"
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
        lines = [f"# 🎖️ Comandos — {self.category}", ""]
        for inv, desc in entries:
            lines.append(f"{inv} — {desc}")
        block = "\n".join(lines)[:3900]

        container = discord.ui.Container(
            discord.ui.TextDisplay(block),
            discord.ui.Separator(),
            discord.ui.ActionRow(_HelpSelect(self.order, self.category)),
            discord.ui.TextDisplay(
                "-# ¿No entendés un término? Usá `/glosario` o el botón 📖 en las tarjetas."
            ),
            accent_colour=_ACCENT,
        )
        self.add_item(container)

    async def show(self, interaction: discord.Interaction, category: str):
        self.category = category
        self._render()
        await interaction.response.edit_message(view=self)
