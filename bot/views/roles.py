"""Persistent button-based role assignment view."""

import discord


class RoleButtonView(discord.ui.View):
    """A single-button view that toggles a role on/off for the clicking user.

    Uses ``timeout=None`` so it survives bot restarts once re-registered
    via ``bot.add_view()``.  The ``custom_id`` must be unique per
    role-button message so Discord can route interactions after a restart.
    """

    def __init__(self, role_id: int, button_label: str, custom_id: str):
        super().__init__(timeout=None)
        self.role_id = role_id

        # Dynamically create the button with the persisted custom_id
        button = discord.ui.Button(
            label=button_label,
            style=discord.ButtonStyle.primary,
            custom_id=custom_id,
        )
        button.callback = self._toggle_role
        self.add_item(button)

    async def _toggle_role(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "Este boton solo funciona en un servidor.", ephemeral=True
            )
            return

        role = guild.get_role(self.role_id)
        if role is None:
            await interaction.response.send_message(
                "El rol configurado ya no existe.", ephemeral=True
            )
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "No se pudo verificar tu usuario.", ephemeral=True
            )
            return

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(
                f"Se te removio el rol **{role.name}**.", ephemeral=True
            )
        else:
            await member.add_roles(role)
            await interaction.response.send_message(
                f"Se te asigno el rol **{role.name}**.", ephemeral=True
            )
