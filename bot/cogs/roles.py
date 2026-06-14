"""Roles cog -- message command, reaction-based role assignment, and
button-based persistent role assignment.

Stores role configs per guild (not global bot attributes) to fix the
duplicate-handler / single-config bug from the original bot.

Button role configs are persisted in bot/data/roles.json so they survive
restarts.
"""

import json
import logging
import os
from pathlib import Path

import discord
from discord.ext import commands

from bot.views.roles import RoleButtonView

logger = logging.getLogger(__name__)

_ROLES_JSON = Path(__file__).resolve().parent.parent / "data" / "roles.json"


def _load_button_configs() -> list[dict]:
    """Load persisted button-role configs from disk."""
    if _ROLES_JSON.exists():
        with open(_ROLES_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_button_configs(configs: list[dict]) -> None:
    """Persist button-role configs to disk."""
    _ROLES_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(_ROLES_JSON, "w", encoding="utf-8") as f:
        json.dump(configs, f, indent=2)


class Roles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Per-guild role configs: {guild_id: {message_id: (emoji_str, role_id)}}
        self._configs: dict[int, dict[int, tuple[str, int]]] = {}
        # Button role configs loaded from JSON
        self._button_configs: list[dict] = _load_button_configs()

    async def cog_load(self):
        """Re-register all persistent RoleButtonViews on cog load."""
        for cfg in self._button_configs:
            custom_id = cfg["custom_id"]
            role_id = cfg["role_id"]
            button_label = cfg["button_label"]
            view = RoleButtonView(role_id, button_label, custom_id)
            self.bot.add_view(view)

    # ── -message <emoji> <role_name> <message text> ─────────────────────
    # (Backward-compatible reaction-based role assignment)

    @commands.command(name="message")
    async def message_cmd(self, ctx: commands.Context, emoji: str, role_name: str, *, message: str):
        """Envia un mensaje con reaccion; los usuarios que reaccionen reciben un rol."""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("No tienes permisos para usar este comando.")
            return

        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if not role:
            await ctx.send(f"El rol '{role_name}' no existe.")
            return

        msg = await ctx.send(message)
        await msg.add_reaction(emoji)

        # Store config per guild
        guild_configs = self._configs.setdefault(ctx.guild.id, {})
        guild_configs[msg.id] = (emoji, role.id)

        await ctx.send(
            f"Mensaje enviado y reaccion {emoji} agregada. "
            f"Los usuarios que reaccionen recibiran el rol '{role_name}'."
        )

    # ── -boton_rol <role_name> <button_label> <message_text> ────────────

    @commands.command(name="boton_rol")
    async def boton_rol_cmd(
        self,
        ctx: commands.Context,
        role_name: str,
        button_label: str,
        *,
        message_text: str,
    ):
        """Envia un mensaje con un boton; al presionarlo se asigna/quita un rol."""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("No tienes permisos para usar este comando.")
            return

        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if not role:
            await ctx.send(f"El rol '{role_name}' no existe.")
            return

        # Build a unique custom_id so the view persists across restarts
        custom_id = f"role_btn:{ctx.guild.id}:{role.id}"

        view = RoleButtonView(role.id, button_label, custom_id)
        msg = await ctx.send(message_text, view=view)

        # Persist config
        cfg = {
            "guild_id": ctx.guild.id,
            "channel_id": ctx.channel.id,
            "message_id": msg.id,
            "role_id": role.id,
            "button_label": button_label,
            "custom_id": custom_id,
        }
        self._button_configs.append(cfg)
        _save_button_configs(self._button_configs)

        # Also register the view globally so it works right away
        self.bot.add_view(view)

        await ctx.send(
            f"Mensaje con boton creado. Los usuarios pueden presionar "
            f"**{button_label}** para recibir/quitar el rol '{role_name}'.",
            delete_after=10,
        )

    # ── Reaction add ────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        guild_configs = self._configs.get(payload.guild_id)
        if not guild_configs:
            return

        config = guild_configs.get(payload.message_id)
        if not config:
            return

        emoji_str, role_id = config
        if str(payload.emoji) != emoji_str:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if not member:
            return

        role = guild.get_role(role_id)
        if role:
            await member.add_roles(role)
            try:
                await member.send(
                    f"Has recibido el rol '{role.name}' por reaccionar con {payload.emoji}!"
                )
            except discord.Forbidden:
                pass  # DMs disabled
        else:
            try:
                await member.send("El rol no existe o no se pudo asignar.")
            except discord.Forbidden:
                pass

    # ── Reaction remove ─────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        guild_configs = self._configs.get(payload.guild_id)
        if not guild_configs:
            return

        config = guild_configs.get(payload.message_id)
        if not config:
            return

        emoji_str, role_id = config
        if str(payload.emoji) != emoji_str:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if not member:
            return

        role = guild.get_role(role_id)
        if role:
            await member.remove_roles(role)
            try:
                await member.send(
                    f"El rol '{role.name}' ha sido removido al quitar la reaccion de {payload.emoji}."
                )
            except discord.Forbidden:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Roles(bot))
