"""Interactive views for the stats cog."""

import discord

from bot.utils import find_player, standard_footer


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

        # Misma tarjeta "versus" que -compare (sin botón Invertir: no hay ctx de comando).
        from bot.ui.comparison_card import ComparisonCard
        metrics = [
            ("Performance", p1.get("Performance Score", 0), p2.get("Performance Score", 0), True),
            ("K/D", p1.get("K/D Ratio", 0), p2.get("K/D Ratio", 0), True),
            ("Kills/Ronda", p1.get("Kills per Round", 0), p2.get("Kills per Round", 0), True),
            ("Deaths/Ronda", p1.get("Deaths per Round", 0), p2.get("Deaths per Round", 0), False),
            ("Score/Ronda", p1.get("Score per Round", 0), p2.get("Score per Round", 0), True),
            ("Rondas", p1.get("Rounds", 0), p2.get("Rounds", 0), True),
            ("Total Kills", p1.get("Total Kills", 0), p2.get("Total Kills", 0), True),
        ]
        warning = None
        few = [p["Player"] for p in (p1, p2) if p.get("Rounds", 0) < 50]
        if few:
            warning = f"Pocas rondas ({', '.join(few)}): los stats pueden no ser representativos."
        card = ComparisonCard(
            None, None, p1["Player"], p2["Player"], metrics=metrics, warning=warning,
            footer="Datos actualizados " + standard_footer(p1).replace("📅 ", ""),
        )
        await interaction.followup.send(view=card)


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
