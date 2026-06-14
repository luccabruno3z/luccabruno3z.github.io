"""Tips cog -- tips command loading from bot/data/tips.json."""

import json
import logging
import os
import random

import discord
from discord.ext import commands
from discord import app_commands

from bot.config import BOT_THUMBNAIL, BASE_URL, performance_color
from bot.utils import format_number, find_player, progress_bar, standard_footer
from bot.assets.kit_mapping import get_kit_display

logger = logging.getLogger(__name__)

# Path to the tips JSON file (relative to the repo root)
_TIPS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "tips.json")

# ── Choices for kit parameter ──────────────────────────────────────────────

async def player_name_autocomplete_tips(
    interaction: discord.Interaction, current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete for player names in tips_para command."""
    try:
        data = await interaction.client.data_fetcher.fetch_all_players()
    except Exception:
        return []
    names = [p["Player"] for p in data]
    if current:
        filtered = [n for n in names if current.lower() in n.lower()]
    else:
        filtered = names
    return [app_commands.Choice(name=n, value=n) for n in filtered[:25]]


# Map tips.json keys -> raw kit names for get_kit_display()
_KIT_KEY_TO_RAW = {
    "rifleman": "rifleman",
    "medic": "medic",
    "automatic rifleman": "automatic_rifleman",
    "grenadier": "grenadier",
    "sniper": "sniper",
    "lat": "lat",
    "hat": "hat",
    "combat engineer": "combat_engineer",
}

KIT_CHOICES = [
    app_commands.Choice(name=get_kit_display(raw), value=key)
    for key, raw in _KIT_KEY_TO_RAW.items()
]


class Tips(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._tips: dict = {}
        self._load_tips()

    def _load_tips(self):
        path = os.path.normpath(_TIPS_FILE)
        with open(path, "r", encoding="utf-8") as f:
            self._tips = json.load(f)

    @commands.hybrid_command(aliases=["consejos", "tip", "consejo"])
    @app_commands.describe(kit="Kit del que quieres recibir consejos")
    @app_commands.choices(kit=KIT_CHOICES)
    async def tips(self, ctx: commands.Context, *, kit: str = None):
        """Proporciona consejos aleatorios según el kit seleccionado."""
        general = self._tips.get("general", [])
        kits = self._tips.get("kits", {})

        if kit is None:
            consejos = random.sample(general, k=min(5, len(general)))
            embed = discord.Embed(
                title="📚 Consejos Generales Aleatorios",
                description="\n".join(f"• {c}" for c in consejos),
                color=discord.Color.blue(),
            )
        else:
            kit_lower = kit.lower()
            if kit_lower in kits:
                kit_tips = kits[kit_lower]
                consejos = random.sample(kit_tips, k=min(5, len(kit_tips)))
                # Get readable display name from kit_mapping
                raw_name = _KIT_KEY_TO_RAW.get(kit_lower, kit_lower)
                display_name = get_kit_display(raw_name)
                embed = discord.Embed(
                    title=f"🎯 Consejos para {display_name}",
                    description="\n".join(f"• {c}" for c in consejos),
                    color=discord.Color.green(),
                )
            else:
                # Build readable kit list from mapping
                kit_list = ", ".join(
                    f"`{get_kit_display(raw)}`" for raw in _KIT_KEY_TO_RAW.values()
                )
                embed = discord.Embed(
                    title="❌ Kit no reconocido",
                    description=(
                        f"Por favor, elige uno de los siguientes kits:\n{kit_list}"
                    ),
                    color=discord.Color.red(),
                )

        embed.set_footer(text="¡Practica y mejora tus habilidades en el campo de batalla!")
        embed.set_thumbnail(url=BOT_THUMBNAIL)
        await ctx.send(embed=embed)

    # ── -tips_para <jugador> ──────────────────────────────────────────────

    @commands.hybrid_command(aliases=["consejospara", "tipspara"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    @app_commands.describe(jugador="Nombre del jugador para consejos personalizados")
    @app_commands.autocomplete(jugador=player_name_autocomplete_tips)
    async def tips_para(self, ctx: commands.Context, *, jugador: str = None):
        """Da consejos personalizados basados en las debilidades de un jugador."""
        if not jugador:
            await ctx.send(
                "❗ Por favor, proporciona un nombre de jugador. "
                "Ejemplo: `-tips_para W4RR10R`."
            )
            return

        try:
            data = await self.bot.data_fetcher.fetch_all_players()
        except Exception as e:
            await ctx.send("❌ Error al conectar con la base de datos. Inténtalo más tarde.")
            logger.error("Error fetching players for tips_para: %s", e)
            return

        jugador_encontrado = find_player(data, jugador)
        if not jugador_encontrado:
            await ctx.send(f"⚠️ Jugador '{jugador}' no encontrado. Probá `-buscar <nombre>` para verificar.")
            return

        nombre = jugador_encontrado["Player"]
        kd = jugador_encontrado.get("K/D Ratio", 0)
        total_deaths = jugador_encontrado.get("Total Deaths", 0)
        rounds_played = jugador_encontrado.get("Rounds", 1)
        kills_per_round = jugador_encontrado.get("Kills per Round", 0)
        score_per_round = jugador_encontrado.get("Score per Round", 0)
        ps = jugador_encontrado.get("Performance Score", 0)
        deaths_per_round = total_deaths / rounds_played if rounds_played > 0 else 0

        # Analyze weaknesses
        improvement = self._tips.get("improvement", {})
        weakness_tips: list[str] = []
        personal_msgs: list[str] = []
        analysis_lines: list[str] = []

        if deaths_per_round > 4.0:
            weakness_tips.extend(improvement.get("survival", []))
            personal_msgs.append(
                f"Con {deaths_per_round:.1f} muertes/ronda, priorizá posicionamiento defensivo y cobertura."
            )
            dpr_bar = progress_bar(deaths_per_round, 8.0, 8)
            analysis_lines.append(f"💀 Muertes/Ronda: **{deaths_per_round:.1f}** `{dpr_bar}` ⚠️ muy alto")
        else:
            dpr_bar = progress_bar(deaths_per_round, 8.0, 8)
            analysis_lines.append(f"💀 Muertes/Ronda: **{deaths_per_round:.1f}** `{dpr_bar}` ✅")

        if kd < 1.0:
            weakness_tips.extend(improvement.get("combat", []))
            personal_msgs.append(
                f"Tu K/D es {kd:.2f} — enfocate en sobrevivir antes de buscar kills."
            )
            kd_bar = progress_bar(kd, 3.0, 8)
            analysis_lines.append(f"💥 K/D: **{kd:.2f}** `{kd_bar}` ⚠️ necesita mejora")
        else:
            kd_bar = progress_bar(kd, 3.0, 8)
            analysis_lines.append(f"💥 K/D: **{kd:.2f}** `{kd_bar}` ✅")

        if kills_per_round < 2.5:
            weakness_tips.extend(improvement.get("aggression", []))
            personal_msgs.append(
                f"Con {kills_per_round:.1f} kills/ronda, intentá ser más agresivo en tus posiciones."
            )
            kpr_bar = progress_bar(kills_per_round, 6.0, 8)
            analysis_lines.append(f"🔫 Kills/Ronda: **{kills_per_round:.1f}** `{kpr_bar}` ⚠️ bajo")
        else:
            kpr_bar = progress_bar(kills_per_round, 6.0, 8)
            analysis_lines.append(f"🔫 Kills/Ronda: **{kills_per_round:.1f}** `{kpr_bar}` ✅")

        if score_per_round < 300:
            weakness_tips.extend(improvement.get("objectives", []))
            personal_msgs.append(
                f"Tu score/ronda es {score_per_round:.0f} — enfocate más en objetivos y captura de puntos."
            )
            spr_bar = progress_bar(score_per_round, 600.0, 8)
            analysis_lines.append(f"🎯 Score/Ronda: **{format_number(score_per_round)}** `{spr_bar}` ⚠️ bajo")
        else:
            spr_bar = progress_bar(score_per_round, 600.0, 8)
            analysis_lines.append(f"🎯 Score/Ronda: **{format_number(score_per_round)}** `{spr_bar}` ✅")

        # If no weaknesses found, give experience tips
        if not weakness_tips:
            weakness_tips.extend(improvement.get("experience", []))
            personal_msgs.append(
                "Tus stats están bien en general. Seguí practicando para llegar al top."
            )

        # Deduplicate and pick random tips
        weakness_tips = list(set(weakness_tips))
        selected_tips = random.sample(weakness_tips, k=min(5, len(weakness_tips)))

        # Limit personal messages to 2
        personal_msgs = personal_msgs[:2]

        color = performance_color(ps)
        embed = discord.Embed(
            title=f"💡 Consejos para {nombre}",
            description="Basados en tu perfil de juego",
            color=color,
        )
        embed.set_thumbnail(url=BOT_THUMBNAIL)

        embed.add_field(
            name="📊 Análisis",
            value="\n".join(analysis_lines),
            inline=False,
        )

        personal_text = "\n".join(f"{i}. {msg}" for i, msg in enumerate(personal_msgs, 1))
        embed.add_field(
            name="🎯 Tips Personalizados",
            value=personal_text,
            inline=False,
        )

        general_text = "\n".join(f"• {tip}" for tip in selected_tips)
        embed.add_field(
            name="📚 Consejos Generales",
            value=general_text,
            inline=False,
        )

        embed.set_footer(text=standard_footer(jugador_encontrado))
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tips(bot))
