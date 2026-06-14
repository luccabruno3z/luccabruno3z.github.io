"""Native Discord polls (community votes, MVP of the week, etc.)."""

import logging
from datetime import timedelta

import discord
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger(__name__)

_NUMBER_EMOJI = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


class Polls(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(aliases=["poll", "votacion", "votación"])
    @app_commands.describe(
        contenido="pregunta | opción1 | opción2 [| ...]  (opcional: agregá '| 48h' para la duración)",
    )
    async def encuesta(self, ctx: commands.Context, *, contenido: str):
        """Crea una encuesta nativa de Discord. Formato: pregunta | op1 | op2 [| 48h]"""
        parts = [p.strip() for p in contenido.split("|") if p.strip()]

        # Duración opcional: último token tipo "48h" / "12h".
        horas = 24
        if parts:
            tok = parts[-1].lower().replace(" ", "")
            if tok.endswith("h") and tok[:-1].isdigit():
                horas = max(1, min(int(tok[:-1]), 32 * 24))  # Discord máx 32 días
                parts = parts[:-1]

        if len(parts) < 3:
            await ctx.send(
                "❗ Formato: `-encuesta pregunta | opción1 | opción2 [| ...]`\n"
                "Ejemplo: `-encuesta ¿MVP de la semana? | juan*ARG* | TheEtern | _JORGE`\n"
                "Duración opcional al final: `... | 48h`",
                ephemeral=True,
            )
            return

        question, options = parts[0], parts[1:11]  # Discord permite hasta 10 respuestas

        poll = discord.Poll(question=question[:300], duration=timedelta(hours=horas))
        for i, opt in enumerate(options):
            poll.add_answer(text=opt[:55], emoji=_NUMBER_EMOJI[i])

        try:
            await ctx.send(poll=poll)
        except discord.HTTPException as exc:
            logger.warning("Poll send failed: %s", exc)
            await ctx.send("❌ No pude crear la encuesta. ¿El canal permite encuestas?", ephemeral=True)

    @commands.hybrid_command(aliases=["mvp_semana"])
    @app_commands.describe(jugadores="Nombres de candidatos separados por coma o '|'")
    async def mvp(self, ctx: commands.Context, *, jugadores: str):
        """Encuesta rápida de MVP con los candidatos dados."""
        sep = "|" if "|" in jugadores else ","
        cands = [c.strip() for c in jugadores.split(sep) if c.strip()][:10]
        if len(cands) < 2:
            await ctx.send("❗ Dame al menos 2 candidatos: `-mvp juan, pedro, ana`", ephemeral=True)
            return
        poll = discord.Poll(question="🏆 MVP de la semana", duration=timedelta(hours=24 * 7))
        for i, c in enumerate(cands):
            poll.add_answer(text=c[:55], emoji=_NUMBER_EMOJI[i])
        try:
            await ctx.send(poll=poll)
        except discord.HTTPException:
            await ctx.send("❌ No pude crear la encuesta en este canal.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Polls(bot))
