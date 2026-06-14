"""Components V2 comparison card for `-compare` (player vs player).

A single Container with the head-to-head metric breakdown, the verdict, an
optional small-sample caution, and an ActionRow: an "Invertir" button plus
per-player demo buttons (reusing the persistent PlayerCardActionButton).
"""

from __future__ import annotations

import discord

from bot.ui.player_card_actions import PlayerCardActionButton

_ACCENT = 0x9B59B6  # purple


class _InvertButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Invertir", emoji="🔁", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        await self.view.invert(interaction)


class ComparisonCard(discord.ui.LayoutView):
    def __init__(
        self,
        cog,
        ctx,
        entity1: str,
        entity2: str,
        *,
        lines: list[str],
        summary: str,
        warning: str | None = None,
        footer: str = "",
        demo_for: list[str] | None = None,
    ):
        super().__init__(timeout=180)
        self.cog = cog
        self.ctx = ctx
        self.entity1 = entity1
        self.entity2 = entity2
        self.message: discord.Message | None = None

        children: list[discord.ui.Item] = [
            discord.ui.TextDisplay(f"# 🔍 {entity1}  ⚔️  {entity2}"),
            discord.ui.Separator(),
            discord.ui.TextDisplay("\n".join(lines)),
            discord.ui.Separator(),
            discord.ui.TextDisplay(summary),
        ]
        if warning:
            children.append(discord.ui.TextDisplay(f"-# ⚠️ {warning}"))
        children.append(discord.ui.Separator(visible=False))
        if footer:
            children.append(discord.ui.TextDisplay(f"-# {footer}"))

        row_items: list[discord.ui.Item] = [_InvertButton()]
        for name in (demo_for or []):
            row_items.append(PlayerCardActionButton("demo", name, label=f"Demo {name}"))
        children.append(discord.ui.ActionRow(*row_items[:5]))  # ActionRow holds <=5

        self.add_item(discord.ui.Container(*children, accent_colour=_ACCENT))

    async def invert(self, interaction: discord.Interaction):
        # Silently acknowledge the click, then post a fresh swapped comparison.
        await interaction.response.defer()
        await self.cog.compare(self.ctx, self.entity2, self.entity1)
