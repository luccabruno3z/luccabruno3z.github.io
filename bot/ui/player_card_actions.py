"""Persistent action buttons for the player card (Components V2 + DynamicItem).

Each button's behaviour is reconstructed from its ``custom_id`` alone, so the
buttons keep working after a bot restart/redeploy — they never go "dead". One
dispatcher class handles all four actions; register it once in setup with
``bot.add_dynamic_items(PlayerCardActionButton)``.

custom_id format: ``pc:<action>:<player_name>`` where action ∈
{demo, hist, cmp, rounds}.
"""

from __future__ import annotations

import re

import discord

from bot.config import BASE_URL, BOT_THUMBNAIL
from bot.services.chart_renderer import render_history_chart
from bot.utils import standard_footer

# action -> button presentation
_ACTIONS = {
    "demo": ("Detalles demo", "📊", discord.ButtonStyle.primary),
    "hist": ("Historial", "📈", discord.ButtonStyle.secondary),
    "cmp": ("Comparar", "⚔️", discord.ButtonStyle.secondary),
    "rounds": ("Últimas rondas", "🎯", discord.ButtonStyle.secondary),
}


def _safe(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", name)


class PlayerCardActionButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"pc:(?P<action>demo|hist|cmp|rounds):(?P<name>.+)",
):
    def __init__(self, action: str, player_name: str, *, label: str | None = None):
        self.action = action
        self.player_name = player_name
        default_label, emoji, style = _ACTIONS[action]
        super().__init__(
            discord.ui.Button(
                label=(label or default_label)[:80],
                emoji=emoji,
                style=style,
                custom_id=f"pc:{action}:{player_name}"[:100],
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        return cls(match["action"], match["name"])

    async def callback(self, interaction: discord.Interaction):
        handler = getattr(self, f"_do_{self.action}")
        await handler(interaction)

    # ── Actions ────────────────────────────────────────────────────────────

    async def _do_cmp(self, interaction: discord.Interaction):
        # Lazy import avoids a circular import at module load.
        from bot.views.stats import CompareModal
        await interaction.response.send_modal(
            CompareModal(self.player_name, interaction.client.data_fetcher)
        )

    async def _do_hist(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        url = f"{BASE_URL}/graphs/history/{_safe(self.player_name)}_history.json"
        try:
            data = await interaction.client.data_fetcher.fetch_json(url, use_stale_on_error=False)
        except Exception:
            data = None
        if not data:
            await interaction.followup.send(
                f"No hay historial para **{self.player_name}**.", ephemeral=True
            )
            return
        dates = [e.get("Date", e.get("date", "?")) for e in data]
        scores = [e.get("Performance Score", 0) for e in data]
        buf = render_history_chart(self.player_name, dates, scores)
        embed = discord.Embed(
            title=f"📈 Historial de {self.player_name}", color=discord.Color.green()
        )
        embed.set_image(url="attachment://history.png")
        embed.set_thumbnail(url=BOT_THUMBNAIL)
        embed.set_footer(text=standard_footer())
        await interaction.followup.send(
            embed=embed, file=discord.File(buf, filename="history.png"), ephemeral=True
        )

    async def _do_demo(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            data = await interaction.client.data_fetcher.fetch_player_details()
        except Exception:
            data = None
        player_data = _find_demo_player(data, self.player_name)
        if player_data is None:
            await interaction.followup.send(
                f"No hay datos de demos para **{self.player_name}**.", ephemeral=True
            )
            return
        # Reuse the proven demo-details embed builder.
        from bot.views.demo_details import DemoDetailsView
        embed = DemoDetailsView(self.player_name, interaction.client)._build_embed(player_data)
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _do_rounds(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        url = f"{BASE_URL}/graphs/demos/player_rounds/{_safe(self.player_name)}.json"
        try:
            data = await interaction.client.data_fetcher.fetch_json(url, use_stale_on_error=False)
        except Exception:
            data = None
        rounds = data.get("rounds") if isinstance(data, dict) else None
        if not rounds:
            await interaction.followup.send(
                f"No hay rondas registradas para **{self.player_name}**.", ephemeral=True
            )
            return
        recent = list(reversed(rounds))[:10]
        lines = []
        for r in recent:
            win = "✅" if r.get("won") else "▫️"
            mapa = str(r.get("map", "?")).replace("_", " ")
            lines.append(
                f"{win} `{r.get('date','?')}` **{mapa}** — "
                f"{r.get('kills',0)}/{r.get('deaths',0)} · {r.get('score',0)} pts"
            )
        embed = discord.Embed(
            title=f"🎯 Últimas rondas — {self.player_name}",
            description="\n".join(lines),
            color=discord.Color.dark_teal(),
        )
        embed.set_footer(text=f"{len(recent)} de {len(rounds)} rondas · {standard_footer()}")
        await interaction.followup.send(embed=embed, ephemeral=True)


def _find_demo_player(data, name: str):
    """Case-insensitive lookup in player_details.json (keyed by 'ign')."""
    if not isinstance(data, list):
        return None
    nl = name.lower()
    for entry in data:
        if entry.get("ign", entry.get("Player", "")).lower() == nl:
            return entry
    for entry in data:
        if nl in entry.get("ign", entry.get("Player", "")).lower():
            return entry
    return None


def build_actions(player_name: str) -> list[PlayerCardActionButton]:
    """The four contextual buttons for a player card."""
    return [PlayerCardActionButton(a, player_name) for a in ("demo", "hist", "cmp", "rounds")]
