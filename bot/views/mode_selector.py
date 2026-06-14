"""Data mode selector view with 3 buttons."""

import discord

from bot.services.guild_settings import VALID_MODES

# Human-readable labels for each mode
MODE_LABELS = {
    "prstats": "\U0001f4e1 PRStats",
    "demos": "\U0001f4e6 Demos",
    "combined": "\U0001f504 Combinado",
}


class ModeSelectorView(discord.ui.View):
    """A 3-button view for selecting the guild's data mode.

    Any guild member can click. The active mode button is highlighted green,
    the rest are grey.
    """

    def __init__(self, guild_settings, guild_id: int, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.guild_settings = guild_settings
        self.guild_id = guild_id
        self.message: discord.Message | None = None
        self._build_buttons()

    def _build_buttons(self) -> None:
        """Create or rebuild the 3 mode buttons with correct styles."""
        self.clear_items()
        current = self.guild_settings.get_mode(self.guild_id)

        for mode in VALID_MODES:
            style = (
                discord.ButtonStyle.success
                if mode == current
                else discord.ButtonStyle.secondary
            )
            button = discord.ui.Button(
                label=MODE_LABELS[mode],
                style=style,
                custom_id=f"mode_select:{mode}",
            )
            button.callback = self._make_callback(mode)
            self.add_item(button)

    def _make_callback(self, mode: str):
        async def callback(interaction: discord.Interaction):
            if interaction.guild is None:
                await interaction.response.send_message(
                    "Este comando solo funciona en un servidor.", ephemeral=True
                )
                return

            self.guild_settings.set_mode(self.guild_id, mode)
            self._build_buttons()

            await interaction.response.edit_message(view=self)
            await interaction.followup.send(
                f"Modo de datos cambiado a **{MODE_LABELS[mode]}**.",
                ephemeral=True,
            )

        return callback

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[union-attr]
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
