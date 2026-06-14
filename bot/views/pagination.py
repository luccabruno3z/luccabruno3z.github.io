"""Reusable pagination view for embeds."""

import discord


class PaginationView(discord.ui.View):
    """A generic paginator that cycles through a list of embeds.

    Args:
        pages: List of embeds to paginate through.
        timeout: Seconds before buttons are disabled (default 180).
        author_id: If set, only this user can interact. If None, anyone can.
    """

    def __init__(
        self,
        pages: list[discord.Embed],
        timeout: float = 180,
        author_id: int | None = None,
    ):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.current = 0
        self.author_id = author_id
        self.message: discord.Message | None = None
        self._update_buttons()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _update_buttons(self):
        self.prev_btn.disabled = self.current == 0
        self.next_btn.disabled = self.current == len(self.pages) - 1
        # Update page counter label
        self.page_label.label = f"{self.current + 1}/{len(self.pages)}"

    # ── Interaction check ────────────────────────────────────────────────────

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Allow everyone, or restrict to the command author if author_id is set."""
        if self.author_id is None:
            return True
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Solo quien invocó el comando puede usar estos botones.",
                ephemeral=True,
            )
            return False
        return True

    # ── Buttons ──────────────────────────────────────────────────────────────

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current = max(0, self.current - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_label(self, interaction: discord.Interaction, button: discord.ui.Button):
        # This button is just a label, not interactive
        await interaction.response.defer()

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current = min(len(self.pages) - 1, self.current + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    # ── Timeout ──────────────────────────────────────────────────────────────

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True  # type: ignore[union-attr]
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
