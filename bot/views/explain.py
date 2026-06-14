"""'¿Cómo se calcula?' button view — shows methodology explanations."""

import discord


# Explanations for each metric/command, keyed by topic
EXPLANATIONS = {
    "teamwork": (
        "🤝 **Teamwork Ratio**\n"
        "Mide qué porcentaje de tu score total viene de acciones de equipo "
        "(revivir, curar, reparar, capturar flags, etc.) en vez de kills.\n\n"
        "**Fórmula:** `Teamwork Score / Score Total`\n\n"
        "• **> 40%** = Muy orientado al equipo\n"
        "• **20-40%** = Balanceado\n"
        "• **< 20%** = Enfocado en combate individual\n\n"
        "Un buen clan necesita jugadores con alto TW ratio (medics, officers) "
        "y otros con alto KPR (riflemen, AT)."
    ),
    "performance": (
        "🌟 **Performance Score v3**\n"
        "Indicador integral usando **percentil rank** para stats de PRStats "
        "y normalización absoluta para datos de demos:\n\n"
        "```\n"
        "20% Combate (K/D, percentil rank)\n"
        "15% Efectividad (KPR, percentil rank)\n"
        "10% Puntuación (SPR, percentil rank)\n"
        "20% Winrate (de demos, 65% WR = máx)\n"
        "15% Teamwork (ratio TW/Score, tope 60%)\n"
        "10% Consistencia (de demos, 0-100)\n"
        "10% Experiencia (rondas, log, tope 1000)\n"
        "```\n\n"
        "Si no hay datos de demos, winrate/teamwork/consistencia "
        "usan valores neutros (0.5).\n\n"
        "**Tiers dinámicos** por percentil: ~5% Elite · ~20% Veterano · "
        "~35% Experimentado · ~30% Soldado · ~10% Recluta\n\n"
        "Los thresholds se recalculan cada vez que corre el scraper. "
        "Penalización sigmoid para jugadores con <54 rondas."
    ),
    "consistencia": (
        "📊 **Consistencia (0-100)**\n"
        "Mide qué tan estable es tu rendimiento ronda a ronda.\n\n"
        "**Fórmula:** `100 - (Coeficiente de Variación × 100)`\n"
        "Donde CV = Desviación Estándar de KPR / Promedio de KPR\n\n"
        "• **> 80** = Muy consistente (rendimiento predecible)\n"
        "• **50-80** = Normal (variación moderada)\n"
        "• **< 50** = Inconsistente (rondas muy buenas y muy malas)\n\n"
        "Un jugador consistente es más confiable para partidas competitivas "
        "que uno con alto promedio pero mucha varianza."
    ),
    "winrate": (
        "🏆 **Tasa de Victoria (Winrate)**\n"
        "Porcentaje de rondas que tu equipo ganó.\n\n"
        "**Fórmula:** `Victorias / (Victorias + Derrotas) × 100`\n\n"
        "Se calcula por:\n"
        "• **General** — todas las rondas\n"
        "• **Por gamemode** — CQ, insurgency, skirmish\n"
        "• **Por facción** — Blufor vs Opfor\n\n"
        "También se comparan tus stats promedio en rondas ganadas vs perdidas "
        "para identificar qué cambia cuando ganás."
    ),
    "dispersion": (
        "📏 **Dispersión de Nivel**\n"
        "Mide la diferencia entre el mejor y peor jugador del clan "
        "en kills por ronda.\n\n"
        "• **Spread > 3** = Alta dependencia (pocos jugadores cargan al clan)\n"
        "• **Spread 1.5-3** = Media (diferencia normal entre roles)\n"
        "• **Spread < 1.5** = Baja (clan parejo, todos contribuyen similar)\n\n"
        "Un clan con alta dispersión es vulnerable: si los top no juegan, "
        "el rendimiento cae mucho."
    ),
    "radar": (
        "📋 **Radar de Perfil (6 ejes)**\n"
        "Cada eje va de 0 a 1, pre-computado por el scraper:\n\n"
        "• **Letalidad** — Kills por ronda (percentil)\n"
        "• **Supervivencia** — 60% K/D percentil + 40% inverso de DPR\n"
        "• **Trabajo en Equipo** — Teamwork ratio + revives + flags\n"
        "• **Impacto** — Winrate + clutch factor + PS\n"
        "• **Consistencia** — Estabilidad del rendimiento + experiencia\n"
        "• **Versatilidad** — Diversidad de kits (1 - índice HHI)\n\n"
        "La línea naranja es el promedio del clan para comparar."
    ),
    "ratings": (
        "📊 **Índices Compuestos (0-100)**\n"
        "4 ratings que capturan dimensiones diferentes del rendimiento:\n\n"
        "⚔️ **Combate** — K/D, KPR, supervivencia, score\n"
        "🎯 **Táctico** — Teamwork, revives, winrate, flags, vehículos\n"
        "🛡️ **Fiabilidad** — Experiencia, consistencia, rachas de derrotas\n"
        "💥 **Impacto** — Winrate sobre 50%, clutch factor, KPR top\n\n"
        "Cada rating se penaliza con sigmoid para jugadores con pocas rondas "
        "(excepto Fiabilidad, que ya incluye experiencia)."
    ),
    "arquetipos": (
        "🎭 **Sistema de Arquetipos**\n"
        "Clasifica a cada jugador en 1 de 11 roles basándose en:\n\n"
        "**Por kit usado (demos):**\n"
        "💉 Médico · 📡 Oficial · 🛡️ Tanquista · 💥 Demoledor\n\n"
        "**Por perfil de stats:**\n"
        "🎯 Francotirador · 🗡️ Asesino · 🛡️ Superviviente · "
        "🏋️ Tanque · ⭐ Veterano\n\n"
        "**Fallback:**\n"
        "🌱 Novato (<30 rondas) · ⚔️ Soldado (default)\n\n"
        "Prioridad: Kit > Stats > Fallback"
    ),
    "clan_fortalezas": (
        "📋 **Análisis FODA del Clan**\n"
        "Compara 4 métricas del clan contra el promedio de todos los clanes:\n\n"
        "• **Kills/ronda** — Capacidad ofensiva\n"
        "• **Trabajo en equipo** — Ratio teamwork score / score total\n"
        "• **Tasa de victoria** — Winrate general\n"
        "• **Consistencia** — Qué tan estable es el rendimiento ronda a ronda. "
        "Se calcula como `100 - (desviación estándar / promedio × 50)` de kills por ronda "
        "(ignorando rondas con 0 kills). Mayor = más predecible.\n\n"
        "🟢 = Por encima del global | 🟡 = Similar | 🔴 = Por debajo\n\n"
        "La **fortaleza** es la métrica donde más superan al promedio. "
        "La **debilidad** es donde más están por debajo."
    ),
}


class ExplainView(discord.ui.View):
    """A button that shows a methodology explanation when clicked."""

    def __init__(self, topic: str, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.topic = topic
        explanation = EXPLANATIONS.get(topic)
        if not explanation:
            self.clear_items()

    @discord.ui.button(
        label="¿Cómo se calcula?",
        style=discord.ButtonStyle.secondary,
        emoji="ℹ️",
    )
    async def explain_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button,
    ):
        text = EXPLANATIONS.get(self.topic, "Sin explicación disponible.")
        embed = discord.Embed(
            title="ℹ️ Metodología",
            description=text,
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
