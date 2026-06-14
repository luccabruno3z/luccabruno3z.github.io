"""Glosario de términos del bot (qué significa cada cosa y de dónde sale).

Definiciones alineadas con el cálculo real en scraper/scoring.py:
- Performance Score v3 (suma ponderada de 7 componentes + penalización sigmoide).
- 4 índices compuestos (0-100), radar de 6 ejes, tiers por percentil, arquetipos.

Se expone como `/glosario` y como botón "📖 Glosario" en las tarjetas.
"""

from __future__ import annotations

import discord

# categoría -> (emoji, [(término, explicación markdown)])
GLOSSARY: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "basicas": ("📊 Métricas básicas", [
        ("K/D (Kill/Death)", "Kills totales ÷ muertes totales. *De dónde:* prstats."),
        ("KPR — Kills/Ronda", "Kills ÷ rondas jugadas. Mide agresividad sostenida. *De dónde:* prstats."),
        ("DPR — Muertes/Ronda", "Muertes ÷ rondas. Más bajo = mejor supervivencia. *De dónde:* prstats."),
        ("SPR — Score/Ronda", "Score ÷ rondas. Aporte total por partida (no solo kills). *De dónde:* prstats."),
        ("Rondas", "Partidas registradas. Base de la confiabilidad estadística. *De dónde:* prstats."),
    ]),
    "performance": ("🌟 Performance Score (v3)", [
        ("Qué es", "Puntaje **0–1** que resume el rendimiento global del jugador."),
        ("Cómo se arma", "Suma ponderada de 7 componentes:\n"
            "• Combate 20% (percentil de K/D)\n"
            "• Efectividad 15% (percentil de KPR)\n"
            "• Score 10% (SPR)\n"
            "• Winrate 20% *(demos)*\n"
            "• Teamwork 15% *(demos)*\n"
            "• Consistencia 10% *(demos)*\n"
            "• Experiencia 10% (escala log de rondas)"),
        ("Penalización sigmoide", "Con pocas rondas el score se reduce: datos con muestra chica no son confiables."),
        ("Tiers", "Se asignan por **percentil** del Performance: 🥇 Elite (~top 5%), Veterano (~20%), "
            "Experimentado (~35%), Soldado (~30%), Recluta (~10%)."),
    ]),
    "indices": ("📈 Índices (0–100)", [
        ("Índice de Combate", "Poder de fuego puro: K/D (35%), KPR (30%), supervivencia/DPR (20%), SPR (15%). "
            "*De dónde:* prstats."),
        ("Índice Táctico", "Juego de equipo y objetivos: teamwork (30%), revives (20%), winrate (20%), "
            "banderas (15%), vehículos (15%). *De dónde:* demos (.PRdemo)."),
        ("Índice de Fiabilidad", "Qué tan estable/confiable: experiencia/rondas (40%), consistencia (35%), "
            "rachas de derrota (25%). *De dónde:* prstats + demos."),
        ("Índice de Impacto", "Cuánto inclina las partidas: winrate (50%), 'clutch' = más kills en victorias "
            "que en derrotas (30%), Performance (20%). *De dónde:* demos."),
    ]),
    "radar": ("🕸️ Radar (6 ejes)", [
        ("Letalidad", "Capacidad de matar (percentil de K/D y KPR)."),
        ("Supervivencia", "0.6·K/D + 0.4·(menos muertes/ronda)."),
        ("Teamwork", "Revives, banderas y teamwork score *(demos)*."),
        ("Impacto", "Winrate + clutch + Performance."),
        ("Consistencia", "Qué tan parejo rinde ronda a ronda (poca variación del KPR)."),
        ("Versatilidad", "Variedad de roles usados (1 − concentración de kits). Más alto = más versátil."),
    ]),
    "arquetipos": ("🎭 Arquetipos", [
        ("Qué son", "Etiqueta automática del estilo de juego, según el perfil del radar + los kits usados."),
        ("Ejemplos", "🏋️ Tanque (domina con consistencia), 🎯 Francotirador (preciso a distancia), "
            "🗡️ Asesino (muy letal pero arriesgado), 🛡️ Superviviente (juega seguro), y más."),
    ]),
    "otros": ("⚙️ Otros términos", [
        ("Activity Index", "Actividad reciente: 40% volumen + 30% engagement (SPR) + 30% impacto (KPR)."),
        ("Consistency score", "Estabilidad del KPR ronda a ronda (menos variación = más consistente). *De dónde:* demos."),
        ("Percentil", "Posición relativa vs. todos los jugadores (ej: top 5%)."),
        ("HHI", "Índice de concentración: qué tan 'casado' está un jugador con un solo kit (alimenta Versatilidad)."),
        ("demos (.PRdemo)", "Grabaciones de partidas de servidores LATAM. Aportan winrate, teamwork, revives, mapas, etc."),
    ]),
}

_ORDER = ["basicas", "performance", "indices", "radar", "arquetipos", "otros"]
_ACCENT = 0x00BBFF


def _category_block(cat: str) -> str:
    title, entries = GLOSSARY[cat]
    lines = [f"# {title}", ""]
    for term, text in entries:
        lines.append(f"**{term}** — {text}")
    return "\n".join(lines)


class _CategorySelect(discord.ui.Select):
    def __init__(self, current: str):
        super().__init__(
            placeholder="Elegí una categoría del glosario",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(label=GLOSSARY[c][0], value=c, default=(c == current))
                for c in _ORDER
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.show(interaction, self.values[0])


class GlossaryView(discord.ui.LayoutView):
    """Glosario navegable por categoría (un Select cambia la página)."""

    def __init__(self, category: str = "basicas"):
        super().__init__(timeout=300)
        self.category = category if category in GLOSSARY else "basicas"
        self._render()

    def _render(self):
        self.clear_items()
        self.add_item(discord.ui.Container(
            discord.ui.TextDisplay(_category_block(self.category)),
            discord.ui.Separator(),
            discord.ui.ActionRow(_CategorySelect(self.category)),
            discord.ui.TextDisplay("-# Tip: abrí el 📖 Glosario desde cualquier tarjeta de stats."),
            accent_colour=_ACCENT,
        ))

    async def show(self, interaction: discord.Interaction, category: str):
        self.category = category
        self._render()
        await interaction.response.edit_message(view=self)
