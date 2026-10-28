"""Top por rol (médicos, anti-tanques, tripulantes…) en Components V2.

Lee demos/role_leaderboards.json (scraper/roles.py). Cada rol se mide por lo que le
toca hacer y se ordena por el valor ajustado por muestra, así una ronda excepcional
no pone a nadie primero; solo entran jugadores con 10+ rondas con el rol y confianza
media o alta. Igual que el leaderboard por período: selects de rol y período que
editan el mensaje.
"""

from __future__ import annotations

import discord

from bot.ui.theme import accent_meter, LIST_SEGMENTS

PERIODS = [("todo", "Todo el historial"), ("mes", "Últimos 30 días")]
_ACCENT = 0xFFA500  # naranja, como el top por rol de la web

# Alias que se aceptan en `-top_rol <rol>` → clave del archivo.
ROLE_ALIASES = {
    "medico": "medico", "médico": "medico", "medic": "medico", "medicos": "medico", "médicos": "medico",
    "at": "at", "antitanque": "at", "anti-tanque": "at", "lat": "at", "hat": "at",
    "tripulante": "tripulante", "tanquista": "tripulante", "crewman": "tripulante", "tanque": "tripulante",
    "piloto": "piloto", "pilot": "piloto",
    "fusilero": "fusilero", "rifleman": "fusilero",
    "tirador": "tirador", "francotirador": "tirador", "sniper": "tirador", "marksman": "tirador",
    "ametrallador": "ametrallador", "mg": "ametrallador",
    "apoyo": "apoyo", "support": "apoyo",
    "asalto": "asalto", "assault": "asalto",
    "especialista": "especialista", "ingeniero": "especialista",
    "oficial": "oficial", "officer": "oficial", "sl": "oficial",
    "observador": "observador", "spotter": "observador",
}
_CONF = {"alta": "confianza alta", "media": "confianza media", "baja": "confianza baja"}


def resolve_role(text: str | None) -> str:
    return ROLE_ALIASES.get((text or "").strip().lower(), "medico")


def _fmt(board: dict, v) -> str:
    if v is None:
        return "—"
    if board.get("metric") == "winrate":
        return f"{round(v * 100)} %"
    return f"{v:.2f}".replace(".", ",")


class _RoleSelect(discord.ui.Select):
    def __init__(self, boards: dict, current: str):
        super().__init__(
            placeholder="Rol", min_values=1, max_values=1,
            options=[discord.SelectOption(label=b.get("label", k), value=k, default=(k == current))
                     for k, b in list(boards.items())[:25]],
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.change(interaction, role=self.values[0])


class _PeriodSelect(discord.ui.Select):
    def __init__(self, current: str):
        super().__init__(
            placeholder="Período", min_values=1, max_values=1,
            options=[discord.SelectOption(label=lbl, value=val, default=(val == current))
                     for val, lbl in PERIODS],
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.change(interaction, period=self.values[0])


class RoleLeaderboardView(discord.ui.LayoutView):
    def __init__(self, fetcher, *, role: str = "medico", period: str = "todo",
                 count: int = 15, author_id: int | None = None):
        super().__init__(timeout=300)
        self.fetcher = fetcher
        self.role = role
        self.period = period
        self.count = max(3, min(count, 20))
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
            self.data = await self.fetcher.fetch_role_leaderboards()
        except Exception:
            self.data = None
        self._render()

    async def change(self, interaction: discord.Interaction, *, role: str | None = None,
                     period: str | None = None):
        self.role = role or self.role
        self.period = period or self.period
        self._render()
        await interaction.response.edit_message(view=self)

    def _render(self):
        self.clear_items()
        periods = (self.data or {}).get("periods") or {}
        boards = periods.get(self.period) or periods.get("todo") or {}
        board = boards.get(self.role)
        plabel = dict(PERIODS).get(self.period, self.period)
        children: list[discord.ui.Item] = []

        if not board:
            children.append(discord.ui.TextDisplay("# 🎖️ Top por rol\n-# Todavía no hay datos por rol."))
        else:
            min_rounds = (self.data or {}).get("min_rounds", 10)
            children.append(discord.ui.TextDisplay(
                f"# 🎖️ Top {board.get('label', self.role)} — {plabel}\n"
                f"-# {board.get('metric_label', '')} · mediana del rol {_fmt(board, board.get('median'))}"
            ))
            players = (board.get("players") or [])[: self.count]
            if not players:
                children.append(discord.ui.TextDisplay(
                    f"-# Nadie llega a {min_rounds} rondas con este rol y confianza suficiente en este período."))
            else:
                top = max(p.get("adjusted", 0) for p in players) or 1
                medals = ["🥇", "🥈", "🥉"]
                podium, lines = [], []
                for i, p in enumerate(players):
                    clan = f"[{p['clan']}] " if p.get("clan") else ""
                    name = discord.utils.escape_markdown(p["player"])
                    if board.get("metric") == "winrate":
                        rec = f"{p.get('wins', 0)}–{p.get('losses', 0)}"
                    else:
                        rec = f"K/D {p.get('kills', 0) / max(p.get('deaths', 0), 1):.2f}".replace(".", ",")
                    detail = (f"{p.get('rounds', 0)} rondas · real {_fmt(board, p.get('value'))} · {rec}"
                              f" · {_CONF.get(p.get('confidence'), '')}")
                    if i < 3:
                        podium.append(f"### {medals[i]} {clan}{name} · `{_fmt(board, p.get('adjusted'))}`\n-# {detail}")
                    else:
                        bar = accent_meter(p.get("adjusted", 0) / top, LIST_SEGMENTS)
                        lines.append(f"{bar} `{i + 1:>2}.` **{clan}{name}** · `{_fmt(board, p.get('adjusted'))}` · {p.get('rounds', 0)} rondas")
                children.append(discord.ui.TextDisplay("\n".join(podium)))
                if lines:
                    children.append(discord.ui.Separator())
                    children.append(discord.ui.TextDisplay("\n".join(lines)))
                children.append(discord.ui.Separator())
                children.append(discord.ui.TextDisplay(
                    f"-# Valor ajustado por muestra (con pocas rondas se acerca a la mediana del rol). "
                    f"Entran jugadores con {min_rounds}+ rondas con el rol y confianza media o alta."
                ))

        if boards:
            children.append(discord.ui.ActionRow(_RoleSelect(boards, self.role)))
        children.append(discord.ui.ActionRow(_PeriodSelect(self.period)))
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
