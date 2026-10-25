"""Vínculo cuenta de Discord → nombre de jugador (IGN), para -vincular y -menu.

Se guarda en DATA_DIR/links.json (volumen persistente en Railway) como
{discord_user_id: ign}.
"""

from __future__ import annotations

from bot.services.storage import JSONStorage

_store: JSONStorage | None = None


def _db() -> JSONStorage:
    global _store
    if _store is None:
        _store = JSONStorage("links.json")
    return _store


def get(user_id: int) -> str | None:
    value = _db().get(str(user_id))
    return value if isinstance(value, str) and value else None


def set(user_id: int, ign: str) -> None:  # noqa: A001 - API corta a propósito
    _db().set(str(user_id), ign)


def delete(user_id: int) -> None:
    _db().delete(str(user_id))
