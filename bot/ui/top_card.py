"""Components V2 card para -top (ranking prstats).

Reemplaza el embed naranja viejo + chart en mensaje separado (que encima se
mandaba aparte cuando había paginación) por una sola tarjeta: ranking en
markdown, gráfico horizontal integrado (MediaGallery) y un Select para cambiar
la métrica en el lugar — sin re-invocar el comando. Sigue el patrón de
LeaderboardView (bot/ui/leaderboard_card.py).
"""

from __future__ import annotations

import discord

from bot.assets.clan_mapping import get_clan_emoji
from bot.config import METRIC_KEY_MAP, MIN_ROUNDS
from bot.services.chart_renderer import render_top_chart
from bot.ui.theme import meter, accent_meter, LIST_SEGMENTS
from bot.utils import format_number, rank_medal, tier_emoji

_ACCENT = 0xFFD700  # dorado, como LeaderboardView
_CHART_FILENAME = "top_chart.png"
_CHART_MAX = 15  # barras máximas (más no se lee)
_PAGE = 10       # filas por página (el podio ocupa las 3 primeras de la página 1)

METRIC_LABELS = {
    "performance": "Performance",
    "kd": "K/D",
    "kills": "Kills",
    "deaths": "Deaths",
    "rounds": "Rondas",
    "score": "Score",
}

# Set de métricas para el modo demos (player_details no tiene Performance Score;
# el resto se normaliza a las claves prstats antes de armar la tarjeta).
DEMO_METRIC_LABELS = {k: v for k, v in METRIC_LABELS.items() if k != "performance"}


def _fmt_value(metric: str, v) -> str:
    if metric in ("performance", "kd"):
        return f"{v:.2f}"
    return format_number(v)


class _MetricSelect(discord.ui.Select):
    def __init__(self, current: str, labels: dict[str, str]):
        super().__init__(
            placeholder="Métrica",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(label=lbl, value=val, default=(val == current))
                for val, lbl in labels.items()
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.change_metric(interaction, self.values[0])


class TopCard(discord.ui.LayoutView):
    """Ranking de -top con métrica intercambiable y chart integrado."""

    def __init__(
        self,
        players: list[dict],
        *,
        categoria_label: str,
        cantidad: int,
        metrica: str,
        excluded: int = 0,
        footer: str = "",
        author_id: int | None = None,
        thresholds: dict | None = None,
        metric_labels: dict[str, str] | None = None,
        subtitle: str | None = None,
        show_tier: bool = True,
    ):
        super().__init__(timeout=300)
        self.players = players  # ya filtrados por MIN_ROUNDS (y activos si aplica)
        self.categoria_label = categoria_label
        self.cantidad = cantidad
        self.metric_labels = metric_labels or METRIC_LABELS
        # Si la métrica pedida no existe en este set (p.ej. performance en demos),
        # caer a la primera disponible.
        self.metrica = metrica if metrica in self.metric_labels else next(iter(self.metric_labels))
        self.excluded = excluded
        self.footer = footer
        self.author_id = author_id
        self.thresholds = thresholds
        self.subtitle = subtitle  # None → default "Mínimo X rondas [· excluidos]"
        # Tier emoji solo tiene sentido para rankings de JUGADORES por performance
        # (los umbrales son de jugadores; en promedios de clan serían engañosos).
        self.show_tier = show_tier
        self.message: discord.Message | None = None
        self.page = 0
        self._render()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.author_id is None or interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message(
            "❌ Solo quien invocó el comando puede cambiar la métrica.", ephemeral=True
        )
        return False

    # ── data helpers ─────────────────────────────────────────────────────────
    def _ranked(self) -> list[dict]:
        key = METRIC_KEY_MAP.get(self.metrica, self.metrica)
        return sorted(self.players, key=lambda p: p.get(key, 0), reverse=True)[: self.cantidad]

    def _pages(self) -> int:
        return max(1, -(-len(self._ranked()) // _PAGE))

    def build_chart_file(self) -> discord.File:
        key = METRIC_KEY_MAP.get(self.metrica, self.metrica)
        label = self.metric_labels.get(self.metrica, self.metrica)
        top = self._ranked()[self.page * _PAGE:][:_CHART_MAX]
        buf = render_top_chart(
            [p.get("Player", "?") for p in top],
            [p.get(key, 0) for p in top],
            label,
            f"Top {len(top)} — {self.categoria_label} · {label}",
        )
        return discord.File(buf, filename=_CHART_FILENAME)

    # ── render ───────────────────────────────────────────────────────────────
    def _render(self):
        self.clear_items()
        key = METRIC_KEY_MAP.get(self.metrica, self.metrica)
        label = self.metric_labels.get(self.metrica, self.metrica)
        ranked = self._ranked()
        self.page = min(self.page, self._pages() - 1)
        top_value = (ranked[0].get(key, 0) or 0) if ranked else 0

        def bar(v) -> str:
            # Performance: color por tier (mismos umbrales que el rango). Resto: cian.
            if self.metrica == "performance" and self.show_tier:
                return meter(v or 0, self.thresholds, length=LIST_SEGMENTS)
            return accent_meter((v or 0) / top_value if top_value else 0, LIST_SEGMENTS)

        podium_lines, lines = [], []
        start = self.page * _PAGE
        for i, p in enumerate(ranked[start:start + _PAGE], start=start + 1):
            medal = rank_medal(i) if i <= 3 else f"`{i:>2}.`"
            clan = p.get("Clan", "")
            emoji = get_clan_emoji(clan)
            # Si la fila ES un clan (rankings de -promedios: Player == Clan), no
            # repetir el tag entre corchetes; el emoji sí suma.
            clan_bit = f" {emoji}" if emoji else (
                f" [{clan}]" if clan and clan != p.get("Player") else ""
            )
            value = _fmt_value(self.metrica, p.get(key, 0))
            tier = (
                f" {tier_emoji(p.get(key, 0), self.thresholds)}"
                if self.show_tier and self.metrica == "performance" else ""
            )
            if i <= 3:
                podium_lines.append(f"### {medal} {p.get('Player', '?')}{clan_bit} · `{value}`{tier}")
            else:
                lines.append(f"{bar(p.get(key, 0))} `{i:>2}.` **{p.get('Player', '?')}**{clan_bit} · `{value}`{tier}")

        subtitle = self.subtitle if self.subtitle is not None else (
            f"Mínimo {MIN_ROUNDS} rondas"
            + (f" · {self.excluded} excluidos" if self.excluded else "")
        )
        children: list[discord.ui.Item] = [
            discord.ui.TextDisplay(f"# 🏆 Top {len(ranked)} — {self.categoria_label} · {label}"),
            discord.ui.TextDisplay(f"-# {subtitle}"),
        ]
        if podium_lines:
            children += [discord.ui.TextDisplay("\n".join(podium_lines)), discord.ui.Separator()]
        if lines or not podium_lines:
            children.append(discord.ui.TextDisplay(
                "\n".join(lines) if lines else "No hay jugadores con suficientes rondas en esta categoría."
            ))
        if ranked:
            children.append(
                discord.ui.MediaGallery(discord.MediaGalleryItem(f"attachment://{_CHART_FILENAME}"))
            )
        if self.footer:
            children.append(discord.ui.TextDisplay(f"-# {self.footer}"))
        children.append(discord.ui.ActionRow(_MetricSelect(self.metrica, self.metric_labels)))
        nav = []
        if self._pages() > 1:
            prev = discord.ui.Button(label="◀", style=discord.ButtonStyle.secondary, disabled=self.page == 0)
            prev.callback = lambda it: self.change_page(it, -1)
            pos = discord.ui.Button(label=f"{self.page + 1} / {self._pages()}", disabled=True,
                                    style=discord.ButtonStyle.secondary)
            nxt = discord.ui.Button(label="▶", style=discord.ButtonStyle.secondary,
                                    disabled=self.page >= self._pages() - 1)
            nxt.callback = lambda it: self.change_page(it, 1)
            nav += [prev, pos, nxt]
        nav.append(discord.ui.Button(label="Ver en la web", style=discord.ButtonStyle.link,
                                     url="https://luccabruno3z.github.io/#/rankings"))
        children.append(discord.ui.ActionRow(*nav))
        self.add_item(discord.ui.Container(*children, accent_colour=_ACCENT))

    async def change_page(self, interaction: discord.Interaction, delta: int):
        self.page = max(0, min(self._pages() - 1, self.page + delta))
        self._render()
        await interaction.response.edit_message(view=self, attachments=[self.build_chart_file()])

    async def change_metric(self, interaction: discord.Interaction, metrica: str):
        self.metrica = metrica
        self.page = 0
        self._render()
        await interaction.response.edit_message(view=self, attachments=[self.build_chart_file()])

    async def on_timeout(self):
        if not self.message:
            return
        try:
            for item in self.walk_children():
                if isinstance(item, (discord.ui.Select, discord.ui.Button)) and not getattr(item, "url", None):
                    item.disabled = True
            await self.message.edit(view=self)
        except Exception:
            pass
