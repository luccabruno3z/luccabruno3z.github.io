"""Suggestions cog — buzón de observaciones/sugerencias de usuarios.

`-sugerencia <texto>` (alias sug): cualquiera deja una observación → se guarda en
`bot/data/suggestions.json` (lista JSON, escritura atómica). `-expsug` (owner): exporta
todo como adjunto .json + un resumen.

Persistencia: por ahora solo el archivo. ⚠️ El disco de Railway es efímero (se borra en
cada redeploy), así que conviene correr `-expsug` cada tanto. El espejo a un canal privado
de Discord (almacenamiento permanente) está preparado como hook futuro: definí la env var
`SUGGESTIONS_LOG_CHANNEL` con el id del canal y `_mirror` empieza a re-postear cada
sugerencia ahí (pendiente del OK del dueño del server).
"""

import io
import json
import logging
import os
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands

from bot.services.storage import DATA_DIR

logger = logging.getLogger(__name__)

_FILE = os.path.join(DATA_DIR, "suggestions.json")
_TZ = timezone(timedelta(hours=-3))  # hora de Argentina
MAX_LEN = 1000


def _load() -> list:
    if os.path.exists(_FILE):
        try:
            with open(_FILE, encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("No se pudo leer %s: %s", _FILE, exc)
    return []


def _save(items: list) -> None:
    """Escritura atómica (temp + replace) para no corromper el .json ante un crash."""
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = _FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _FILE)


class Suggestions(commands.Cog):
    """Buzón de sugerencias/observaciones."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _mirror(self, entry: dict) -> None:
        """Hook futuro: re-postea la sugerencia a un canal privado (almacenamiento
        permanente en Discord). No-op hasta configurar SUGGESTIONS_LOG_CHANNEL."""
        ch_id = os.getenv("SUGGESTIONS_LOG_CHANNEL")
        if not ch_id:
            return
        try:
            channel = self.bot.get_channel(int(ch_id))
            if channel is None:
                return
            embed = discord.Embed(description=entry["content"], color=0x00FFFF)
            embed.set_author(name=f"#{entry['id']} · {entry['author']}")
            embed.set_footer(text=f"canal: {entry.get('channel') or 'DM'} · {entry['ts']}")
            await channel.send(embed=embed)
        except Exception as exc:  # nunca romper el guardado por el espejo
            logger.warning("No se pudo espejar la sugerencia #%s: %s", entry.get("id"), exc)

    # ── -sugerencia <texto> ──────────────────────────────────────────────────
    # (nombre `sugerencia`; `sugerir` ya lo usa -sugerir_equipo en compare.py)
    @commands.hybrid_command(
        aliases=["sug"],
        description="Dejá una observación o sugerencia para el equipo del bot",
    )
    @commands.cooldown(3, 300, commands.BucketType.user)  # 3 cada 5 min por usuario
    async def sugerencia(self, ctx: commands.Context, *, contenido: str):
        """Guarda una observación/sugerencia del usuario."""
        contenido = (contenido or "").strip()
        if not contenido:
            await ctx.send("Escribí algo después del comando. Ej: `-sugerencia el -top tarda en cargar`")
            return
        if len(contenido) > MAX_LEN:
            contenido = contenido[:MAX_LEN] + "…"

        items = _load()
        entry = {
            "id": (items[-1]["id"] + 1) if items else 1,
            "ts": datetime.now(_TZ).isoformat(timespec="seconds"),
            "author": str(ctx.author),
            "author_id": ctx.author.id,
            "guild": ctx.guild.name if ctx.guild else None,
            "channel": getattr(ctx.channel, "name", None),
            "content": contenido,
            "status": "new",
        }
        items.append(entry)
        _save(items)
        await self._mirror(entry)
        await ctx.send(f"✅ ¡Gracias por tu aporte! Quedó registrada como sugerencia **#{entry['id']}**.")

    @sugerencia.error
    async def sugerencia_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"Tranqui 🙂 ya mandaste varias; probá de nuevo en {error.retry_after:.0f}s.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Te falta el texto: `-sugerencia <tu observación>`.")

    # ── -expsug (owner) ──────────────────────────────────────────────────────
    @commands.command(aliases=["expsugerencias", "exportsug"])
    @commands.is_owner()
    async def expsug(self, ctx: commands.Context):
        """Exporta todas las sugerencias como .json + un resumen. Solo el dueño del bot."""
        items = _load()
        if not items:
            await ctx.send("Todavía no hay sugerencias guardadas.")
            return

        buf = io.BytesIO(json.dumps(items, ensure_ascii=False, indent=2).encode("utf-8"))
        file = discord.File(buf, filename="sugerencias.json")

        recientes = "\n".join(
            f"**#{i['id']}** · {discord.utils.escape_markdown(i['author'])}: "
            f"{discord.utils.escape_markdown(i['content'][:80])}"
            for i in items[-5:]
        )
        embed = discord.Embed(
            title=f"📥 {len(items)} sugerencias registradas",
            description=f"Últimas:\n{recientes}",
            color=0x00FFFF,
        )
        embed.set_footer(text=f"Desde {items[0]['ts'][:10]} hasta {items[-1]['ts'][:10]} · "
                              f"⚠️ el disco de Railway es efímero, exportá cada tanto")
        await ctx.send(embed=embed, file=file)

    @expsug.error
    async def expsug_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.NotOwner):
            await ctx.send("Solo el dueño del bot puede exportar las sugerencias.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Suggestions(bot))
