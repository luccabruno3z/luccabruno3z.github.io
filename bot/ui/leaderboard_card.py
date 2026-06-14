"""Components V2 leaderboard with interactive period/metric selects.

Replaces the `top_periodo` embed + bar-chart PNG with a LayoutView: a single
Container holding the ranking as markdown plus two StringSelects (period and
metric). Changing a select re-fetches/re-sorts and edits the message in place —
no need for the 7 command aliases.
"""

from __future__ import annotations

import discord

from bot.utils import format_number

PERIODS = [("dia", "Hoy"), ("semana", "Semana"), ("mes", "Mes"), ("todo", "Todo")]
METRICS = [("kills", "Kills"), ("kd", "K/D"), ("score", "Score"),
           ("revives", "Revives"), ("teamwork", "Teamwork")]
_PERIOD_LABEL = {"dia": "Hoy", "semana": "Última semana", "mes": "Último mes",
                 "todo": "Todo el historial"}
_ACCENT = 0xFFD700  # gold


def _metric_funcs(metric: str):
    """Return (sort_key_fn, label, value_fmt_fn) for a metric."""
    if metric == "kd":
        kf = lambda p: (p["kills"] / p["deaths"]) if p.get("deaths", 0) > 0 else float(p.get("kills", 0))
        return kf, "K/D", lambda p: f"{kf(p):.2f}"
    if metric == "score":
        return (lambda p: p.get("score", 0)), "Score", lambda p: format_number(p.get("score", 0))
    if metric == "revives":
        return (lambda p: p.get("revives", 0)), "Revives", lambda p: str(p.get("revives", 0))
    if metric == "teamwork":
        return (lambda p: p.get("teamwork_score", 0)), "Teamwork", lambda p: format_number(p.get("teamwork_score", 0))
    return (lambda p: p.get("kills", 0)), "Kills", lambda p: str(p.get("kills", 0))


class _PeriodSelect(discord.ui.Select):
    def __init__(self, current: str):
        super().__init__(
            placeholder="Período",
            min_values=1, max_values=1,
            options=[discord.SelectOption(label=lbl, value=val, default=(val == current))
                     for val, lbl in PERIODS],
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.change_period(interaction, self.values[0])


class _MetricSelect(discord.ui.Select):
    def __init__(self, current: str):
        super().__init__(
            placeholder="Métrica",
            min_values=1, max_values=1,
            options=[discord.SelectOption(label=lbl, value=val, default=(val == current))
                     for val, lbl in METRICS],
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.change_metric(interaction, self.values[0])


class LeaderboardView(discord.ui.LayoutView):
    def __init__(self, fetcher, *, period: str = "semana", metric: str = "kills",
                 count: int = 15, author_id: int | None = None):
        super().__init__(timeout=300)
        self.fetcher = fetcher
        self.period = period
        self.metric = metric
        self.count = max(1, min(count, 50))
        self.author_id = author_id
        self.data = None
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.author_id is None or interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message(
            "❌ Solo quien invocó el comando puede cambiar estos filtros.", ephemeral=True
        )
        return False

    async def load(self):
        try:
            self.data = await self.fetcher.fetch_leaderboard(self.period)
        except Exception:
            self.data = None
        self._render()

    async def change_period(self, interaction: discord.Interaction, period: str):
        self.period = period
        try:
            self.data = await self.fetcher.fetch_leaderboard(period)
        except Exception:
            self.data = None
        self._render()
        await interaction.response.edit_message(view=self)

    async def change_metric(self, interaction: discord.Interaction, metric: str):
        self.metric = metric
        self._render()
        await interaction.response.edit_message(view=self)

    def _render(self):
        self.clear_items()

        if isinstance(self.data, dict):
            players = self.data.get("players", []) or []
            total = self.data.get("total_rounds", 0)
        else:
            players = self.data or []
            total = 0

        key_fn, label, fmt = _metric_funcs(self.metric)
        plabel = _PERIOD_LABEL.get(self.period, self.period)
        children: list[discord.ui.Item] = [
            discord.ui.TextDisplay(f"# 🏆 Top {label} — {plabel}")
        ]

        if not players:
            children.append(discord.ui.TextDisplay("-# No hay rondas en este período todavía."))
        else:
            ranked = sorted(players, key=key_fn, reverse=True)[: self.count]
            medals = ["🥇", "🥈", "🥉"]
            lines = []
            for i, p in enumerate(ranked):
                medal = medals[i] if i < 3 else f"`{i + 1:>2}.`"
                lines.append(
                    f"{medal} **{p['ign']}** — {fmt(p)}  "
                    f"-# {p.get('rounds', 0)}R · {p.get('kills', 0)}K/{p.get('deaths', 0)}D"
                )
            children.append(discord.ui.TextDisplay("\n".join(lines)))
            children.append(discord.ui.Separator())
            children.append(discord.ui.TextDisplay(
                f"-# 📊 {format_number(total)} rondas · {len(players)} jugadores de clanes"
            ))

        children.append(discord.ui.ActionRow(_PeriodSelect(self.period)))
        children.append(discord.ui.ActionRow(_MetricSelect(self.metric)))
        self.add_item(discord.ui.Container(*children, accent_colour=_ACCENT))

    async def on_timeout(self):
        if not self.message:
            return
        try:
            for item in self.walk_children():
                if isinstance(item, discord.ui.Select):
                    item.disabled = True
            await self.message.edit(view=self)
        except Exception:
            pass
