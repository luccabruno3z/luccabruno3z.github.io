"""Components V2 comparison card para -compare y el botón "Comparar" del perfil.

Un Container: encabezado con la leyenda de colores (🟦 jugador 1 · 🟧 jugador 2),
el veredicto arriba, cada métrica como bloque "versus" con barra dividida
(bot.ui.versus), el bloque opcional de demos (no cuenta para el veredicto), el
radar en MediaGallery y botones (Invertir + Demo de cada jugador).
"""

from __future__ import annotations

import discord

from bot.config import BOT_THUMBNAIL
from bot.ui.player_card_actions import PlayerCardActionButton
from bot.ui.theme import ACCENT
from bot.ui.versus import versus_lines, verdict, legend


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
        metrics: list[tuple],
        warning: str | None = None,
        footer: str = "",
        demo_for: list[str] | None = None,
        radar_filename: str | None = None,
        demo_metrics: list[tuple] | None = None,
        demo_note: str | None = None,
    ):
        super().__init__(timeout=180)
        self.cog = cog
        self.ctx = ctx
        self.entity1 = entity1
        self.entity2 = entity2
        self.message: discord.Message | None = None

        body, w1, w2, _ties = versus_lines(entity1, entity2, metrics)
        children: list[discord.ui.Item] = [
            discord.ui.Section(
                f"## {entity1} vs {entity2}",
                legend(entity1, entity2),
                verdict(entity1, entity2, w1, w2, len(metrics)),
                accessory=discord.ui.Thumbnail(BOT_THUMBNAIL),
            ),
            discord.ui.Separator(),
            discord.ui.TextDisplay(body),
        ]
        if warning:
            children.append(discord.ui.TextDisplay(f"-# ⚠️ {warning}"))
        if demo_metrics:
            dbody, dw1, dw2, _ = versus_lines(entity1, entity2, demo_metrics)
            children.append(discord.ui.Separator())
            children.append(discord.ui.TextDisplay(
                f"### Demos · {entity1} {dw1} – {dw2} {entity2}\n{dbody}"))
            if demo_note:
                children.append(discord.ui.TextDisplay(f"-# {demo_note}"))
        if radar_filename:
            children.append(
                discord.ui.MediaGallery(discord.MediaGalleryItem(f"attachment://{radar_filename}"))
            )
        if footer:
            children.append(discord.ui.TextDisplay(f"-# {footer}"))

        row_items: list[discord.ui.Item] = [_InvertButton()] if cog is not None else []
        for name in (demo_for or []):
            row_items.append(PlayerCardActionButton("demo", name, label=f"Demos {name}"))
        if row_items:
            children.append(discord.ui.ActionRow(*row_items[:5]))  # ActionRow holds <=5

        self.add_item(discord.ui.Container(*children, accent_colour=ACCENT))

    async def invert(self, interaction: discord.Interaction):
        # Silently acknowledge the click, then post a fresh swapped comparison.
        await interaction.response.defer()
        await self.cog.compare(self.ctx, self.entity2, self.entity1)
