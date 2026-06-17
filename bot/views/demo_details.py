"""Demo details view — button that shows detailed demo stats for a player."""

import discord

from bot.assets.kit_mapping import get_kit_emoji, normalize_kits, clean_vehicle_name, weapon_model_name, is_personal_weapon


def _group_counts(raw: dict, namer, exclude=None) -> dict:
    """Agrupa {code:count} por nombre legible (colapsa variantes) → {nombre:count}."""
    out: dict[str, int] = {}
    for code, cnt in (raw or {}).items():
        if exclude and exclude(code):
            continue
        name = namer(code)
        out[name] = out.get(name, 0) + cnt
    return out
from bot.config import BOT_THUMBNAIL
from bot.utils import format_number, standard_footer


class DemoDetailsView(discord.ui.View):
    """A single-button view that fetches and shows demo-based detailed stats.

    Attributes:
        player_name: The player to look up in demo data.
        bot: Bot reference to access ``bot.data_fetcher``.
    """

    def __init__(self, player_name: str, bot, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.player_name = player_name
        self.bot = bot
        self.message: discord.Message | None = None

    @discord.ui.button(
        label="Detalles Demo",
        style=discord.ButtonStyle.primary,
        emoji="\U0001f4ca",
    )
    async def demo_details_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            data = await self.bot.data_fetcher.fetch_player_details()
        except Exception:
            await interaction.followup.send(
                "No hay datos de demos para este jugador.", ephemeral=True
            )
            return

        if not data:
            await interaction.followup.send(
                "No hay datos de demos para este jugador.", ephemeral=True
            )
            return

        # Find player (case-insensitive) — demo data uses "ign" as key
        player_data = None
        name_lower = self.player_name.lower()
        if isinstance(data, list):
            for entry in data:
                ign = entry.get("ign", entry.get("Player", ""))
                if ign.lower() == name_lower:
                    player_data = entry
                    break
            if player_data is None:
                for entry in data:
                    ign = entry.get("ign", entry.get("Player", ""))
                    if name_lower in ign.lower():
                        player_data = entry
                        break

        if player_data is None:
            await interaction.followup.send(
                "No hay datos de demos para este jugador.", ephemeral=True
            )
            return

        embed = self._build_embed(player_data)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @staticmethod
    def _top3(d: dict) -> list[tuple[str, int]]:
        """Return top 3 items from a dict sorted by value descending."""
        return sorted(d.items(), key=lambda x: x[1], reverse=True)[:3]

    def _build_embed(self, player_data: dict) -> discord.Embed:
        """Build the demo details embed from player data.

        Handles the real JSON format from player_details.json:
        - ign, total_revives_given, total_revives_received,
        - kits_used: {name: count}, kill_weapons: {name: count},
        - vehicle_kills: {name: count}, total_flags_captured
        """
        name = player_data.get("ign", player_data.get("Player", self.player_name))
        rounds = player_data.get("rounds_played", 0)

        embed = discord.Embed(
            title=f"\U0001f4ca Detalles Demo \u2014 {name}",
            color=discord.Color.dark_teal(),
        )

        # Revives
        revives_given = player_data.get("total_revives_given", 0)
        revives_received = player_data.get("total_revives_received", 0)
        embed.add_field(
            name="\U0001fa78 Revives",
            value=f"Dados: **{revives_given}**\nRecibidos: **{revives_received}**",
            inline=True,
        )

        # Top 3 kits (normalized from faction variants)
        raw_kits = player_data.get("kits_used", {})
        if raw_kits:
            normalized = normalize_kits(raw_kits)
            top3 = sorted(normalized.items(), key=lambda x: x[1], reverse=True)[:3]
            lines = []
            for i, (k, v) in enumerate(top3, 1):
                emoji = get_kit_emoji(k)
                label = f"{emoji} {k}" if emoji else k
                lines.append(f"{i}. {label} ({v})")
            embed.add_field(name="\U0001f392 Top Kits", value="\n".join(lines), inline=True)

        # Top 3 weapons agrupadas por modelo (excluye entorno "?")
        weapons_dict = _group_counts(player_data.get("kill_weapons", {}),
                                     weapon_model_name, exclude=lambda c: not is_personal_weapon(c))
        if weapons_dict:
            lines = [f"{i}. **{w}** ({c} kills)" for i, (w, c) in enumerate(self._top3(weapons_dict), 1)]
            embed.add_field(name="\U0001f52b Top Armas", value="\n".join(lines), inline=True)

        # Top 3 vehicles agrupados por nombre
        vehicles_dict = _group_counts(player_data.get("vehicle_kills", {}), clean_vehicle_name)
        if vehicles_dict:
            lines = [f"{i}. **{v}** ({c} kills)" for i, (v, c) in enumerate(self._top3(vehicles_dict), 1)]
            embed.add_field(name="\U0001f681 Top Vehiculos", value="\n".join(lines), inline=True)

        # Flags captured
        flags = player_data.get("total_flags_captured", 0)
        embed.add_field(
            name="\U0001f6a9 Flags Capturadas",
            value=f"**{flags}**",
            inline=True,
        )

        # Teamwork score
        tw = player_data.get("total_teamwork_score", 0)
        if tw > 0:
            embed.add_field(
                name="\U0001f91d Teamwork Score",
                value=f"**{format_number(tw)}**",
                inline=True,
            )

        embed.set_thumbnail(url=BOT_THUMBNAIL)
        if rounds > 0:
            embed.set_footer(text=f"Datos de {rounds} rondas | {standard_footer()}")
        else:
            embed.set_footer(text=standard_footer())

        return embed

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[union-attr]
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
