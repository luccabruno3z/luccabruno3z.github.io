"""Components V2 "player card" — the flagship `-stats` layout.

Replaces the classic Embed + attached matplotlib PNG with a native LayoutView:
a tier-colored Container, a header Section pairing the player's identity with
the clan logo (Thumbnail accessory), native unicode bars for the performance
breakdown (no image round-trip), and an optional ActionRow of contextual
actions (passed in by the cog as persistent DynamicItems).

Self-contained: depends only on `discord`, so it can be unit-built/validated
without importing the rest of the bot.
"""

from __future__ import annotations

import discord

# Tier → accent color for the Container border (mirrors the web/tier palette).
TIER_COLORS: dict[str, int] = {
    "Elite": 0xFFD700,
    "Veterano": 0x00FF88,
    "Experimentado": 0x00BBFF,
    "Soldado": 0xFF8800,
    "Recluta": 0xFF4466,
}
DEFAULT_ACCENT = 0x00FFFF  # cyan, matches the web theme

_BAR_FULL = "▰"
_BAR_EMPTY = "▱"


def bar(value: float, max_value: float = 100.0, length: int = 12) -> str:
    """Unicode meter: bar(70) -> '▰▰▰▰▰▰▰▰▱▱▱▱'."""
    if max_value <= 0:
        return _BAR_EMPTY * length
    filled = int(round((value / max_value) * length))
    filled = max(0, min(length, filled))
    return _BAR_FULL * filled + _BAR_EMPTY * (length - filled)


def _fmt(n) -> str:
    """Thousands separator, es-AR style (1.234.567)."""
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


class PlayerCard(discord.ui.LayoutView):
    """A single-player stats card built with Components V2.

    Args:
        player: row dict from all_players_clusters.json.
        tier_name / tier_emoji: precomputed tier label + emoji.
        archetype: e.g. "🎯 Francotirador".
        ranking_global / ranking_clan: positions (int or "N/A").
        clan_logo_url: absolute URL to the clan logo (Thumbnail accessory).
        breakdown: list of (label, value 0-100) for the native bars.
        footer: small print line (data source / last updated).
        trend: optional "📈"/"📉"/"➡️" suffix for Performance.
        next_tier: optional (name, points_missing) tuple.
        warning: optional caption shown near the bottom (low sample, etc.).
        highlights: optional markdown line(s) (best/worst round).
        accent: optional Container border color (int); falls back to tier color.
        actions: optional list of items (buttons) placed in a trailing ActionRow.
    """

    def __init__(
        self,
        player: dict,
        *,
        tier_name: str,
        tier_emoji: str,
        archetype: str,
        ranking_global,
        ranking_clan,
        clan_logo_url: str,
        breakdown: list[tuple[str, float]],
        footer: str,
        trend: str = "",
        next_tier: tuple[str, float] | None = None,
        warning: str | None = None,
        highlights: str | None = None,
        accent: int | None = None,
        actions: list[discord.ui.Item] | None = None,
    ):
        super().__init__(timeout=None)  # persistent; interactivity via DynamicItems

        name = player.get("Player", "?")
        clan = player.get("Clan", "—")
        kd = player.get("K/D Ratio", 0) or 0
        kpr = player.get("Kills per Round", 0) or 0
        dpr = player.get("Deaths per Round", 0) or 0
        spr = player.get("Score per Round", 0) or 0
        ps = player.get("Performance Score", 0) or 0

        accent_color = accent if accent is not None else TIER_COLORS.get(tier_name, DEFAULT_ACCENT)

        # ── Header: identity + clan logo as accessory ──────────────────────
        header = discord.ui.Section(
            f"## {name}  ·  `{clan}`",
            f"{tier_emoji} **{tier_name}**  ·  {archetype}",
            f"-# Ranking global **#{ranking_global}**  ·  clan **#{ranking_clan}**",
            accessory=discord.ui.Thumbnail(clan_logo_url),
        )

        # ── Core stats as compact markdown (reads well on mobile) ──────────
        stats = discord.ui.TextDisplay(
            "**Combate**\n"
            f"💥 K/D `{kd:.2f}`   🔫 KPR `{kpr:.2f}`   📉 DPR `{dpr:.2f}`\n"
            "**Volumen**\n"
            f"☠️ Kills `{_fmt(player.get('Total Kills', 0))}`   "
            f"💀 Muertes `{_fmt(player.get('Total Deaths', 0))}`\n"
            f"🏆 Score `{_fmt(player.get('Total Score', 0))}`   "
            f"🎮 Rondas `{_fmt(player.get('Rounds', 0))}`\n"
            f"🌟 **Performance** `{ps:.2f}`{trend}   🎯 SPR `{spr:.2f}`"
        )

        # ── Native breakdown bars (replaces the matplotlib PNG) ────────────
        bd_lines = ["**Desglose de rendimiento**"]
        for label, value in breakdown:
            bd_lines.append(f"`{bar(value)}`  {label} · **{value:.0f}**")
        breakdown_block = discord.ui.TextDisplay("\n".join(bd_lines))

        children: list[discord.ui.Item] = [
            header,
            discord.ui.Separator(),
            stats,
            discord.ui.Separator(),
            breakdown_block,
        ]

        if highlights:
            children.append(discord.ui.Separator())
            children.append(discord.ui.TextDisplay(highlights))

        if next_tier:
            nt_name, nt_missing = next_tier
            children.append(discord.ui.TextDisplay(
                f"📈 Próximo tier: **{nt_name}** — te faltan **{nt_missing:.2f}** pts"
            ))

        if warning:
            children.append(discord.ui.TextDisplay(f"-# ⚠️ {warning}"))

        children.append(discord.ui.Separator(visible=False))
        children.append(discord.ui.TextDisplay(f"-# {footer}"))

        if actions:
            children.append(discord.ui.ActionRow(*actions))

        self.add_item(discord.ui.Container(*children, accent_colour=accent_color))
