"""Components V2 comparison card for `-compare` (player vs player).

A single Container: header, the aligned head-to-head table (see utils.versus_table),
the verdict, an optional small-sample caution, the radar chart embedded via
MediaGallery (same message — before it went as a separate embed), and an ActionRow
with "Invertir" plus per-player demo buttons.
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
        table: str,
        summary: str,
        warning: str | None = None,
        footer: str = "",
        demo_for: list[str] | None = None,
        radar_filename: str | None = None,
        demo_table: str | None = None,
        demo_note: str | None = None,
    ):
        super().__init__(timeout=180)
        self.cog = cog
        self.ctx = ctx
        self.entity1 = entity1
        self.entity2 = entity2
        self.message: discord.Message | None = None

        children: list[discord.ui.Item] = [
            discord.ui.TextDisplay(f"# ⚔️ {entity1} vs {entity2}"),
            discord.ui.TextDisplay("-# ▲ marca al mejor en cada categoría"),
            discord.ui.TextDisplay(table),
            discord.ui.TextDisplay(summary),
        ]
        if warning:
            children.append(discord.ui.TextDisplay(f"-# ⚠️ {warning}"))
        if demo_table:
            children.append(discord.ui.Separator())
            children.append(discord.ui.TextDisplay("### 📼 Demos (por ronda)"))
            children.append(discord.ui.TextDisplay(demo_table))
            if demo_note:
                children.append(discord.ui.TextDisplay(f"-# {demo_note}"))
        if radar_filename:
            children.append(
                discord.ui.MediaGallery(discord.MediaGalleryItem(f"attachment://{radar_filename}"))
            )
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
