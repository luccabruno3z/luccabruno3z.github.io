"""Interactive views for the stats cog."""

import discord

from bot.config import BOT_THUMBNAIL
from bot.utils import find_player, format_number, highlight_winner, advantage_pct, standard_footer


class CompareModal(discord.ui.Modal, title="Comparar jugador"):
    """Modal that asks for a second player name to run a quick comparison."""

    other_player = discord.ui.TextInput(
        label="Nombre del otro jugador",
        placeholder="Escribe el nombre del jugador...",
        max_length=50,
    )

    def __init__(self, original_player: str, fetcher):
        super().__init__()
        self.original_player = original_player
        self.fetcher = fetcher

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        other = self.other_player.value.strip()

        try:
            data = await self.fetcher.fetch_all_players()
        except Exception:
            await interaction.followup.send(
                "❌ Error al conectar con la base de datos.", ephemeral=True
            )
            return

        p1 = find_player(data, self.original_player)
        p2 = find_player(data, other)

        if not p1 or not p2:
            missing = []
            if not p1:
                missing.append(self.original_player)
            if not p2:
                missing.append(other)
            await interaction.followup.send(
                f"⚠️ No se encontró a: **{', '.join(missing)}**. Verificá el nombre.",
                ephemeral=True,
            )
            return

        name1 = p1["Player"]
        name2 = p2["Player"]

        metrics = [
            ("💥 K/D", "K/D Ratio", True),
            ("🔫 Kills/Ronda", "Kills per Round", True),
            ("🎯 Score/Ronda", "Score per Round", True),
            ("🌟 Performance", "Performance Score", True),
            ("🎮 Rounds", "Rounds", True),
            ("☠️ Total Kills", "Total Kills", True),
        ]

        lines = []
        p1_wins = 0
        for label, key, higher_better in metrics:
            v1 = p1.get(key, 0)
            v2 = p2.get(key, 0)
            e1, e2 = highlight_winner(v1, v2, higher_better)
            if e1 == "✅":
                p1_wins += 1
            if e1 == "✅":
                lines.append(f"{label}: {e1} **{format_number(v1)}** ({advantage_pct(v1, v2)}) vs {e2} {format_number(v2)}")
            elif e2 == "✅":
                lines.append(f"{label}: {e1} {format_number(v1)} vs {e2} **{format_number(v2)}** ({advantage_pct(v2, v1)})")
            else:
                lines.append(f"{label}: 🟰 {format_number(v1)} vs 🟰 {format_number(v2)}")

        p2_wins = len(metrics) - p1_wins - sum(1 for _, k, _ in metrics if p1.get(k, 0) == p2.get(k, 0))

        if p1_wins > p2_wins:
            verdict = f"**{name1}** gana {p1_wins}/{len(metrics)} categorías"
        elif p2_wins > p1_wins:
            verdict = f"**{name2}** gana {p2_wins}/{len(metrics)} categorías"
        else:
            verdict = f"Empate {p1_wins}/{len(metrics)} categorías cada uno"

        embed = discord.Embed(
            title=f"⚔️ {name1} vs {name2}",
            description="\n".join(lines),
            color=discord.Color.purple(),
        )
        embed.add_field(name="🏆 Veredicto", value=verdict, inline=False)
        embed.set_thumbnail(url=BOT_THUMBNAIL)
        embed.set_footer(text=standard_footer(p1))

        await interaction.followup.send(embed=embed)


class StatsView(discord.ui.View):
    """Buttons attached to -estadisticas: Ver Historial + Comparar."""

    def __init__(self, player_name: str, fetcher, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.player_name = player_name
        self.fetcher = fetcher

    @discord.ui.button(label="Ver Historial", style=discord.ButtonStyle.primary, emoji="\U0001f4c8")
    async def history_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        # Mismo gráfico/búsqueda que el comando -historial (fuente única).
        from bot.services.history_chart import build_history_embed
        embed, file = await build_history_embed(self.fetcher, self.player_name)
        if file:
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send(embed=embed)

    @discord.ui.button(label="Comparar", style=discord.ButtonStyle.secondary, emoji="\U0001f50d")
    async def compare_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CompareModal(self.player_name, self.fetcher)
        await interaction.response.send_modal(modal)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True  # type: ignore[union-attr]
