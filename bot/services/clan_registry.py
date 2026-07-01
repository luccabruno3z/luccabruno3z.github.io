"""Registro de clanes derivado de los datos (data-driven).

La lista de clanes sale de `clan_averages.json` (lo que realmente scrapea el
scraper), no de una lista hardcodeada. Se arma una vez al arrancar el bot
(`bot.clans`) y de ahí salen: el autocomplete de clanes, las categorías de
`-top`, la URL de JSON por clan y los atajos `-grafico<clan>`.

Agregar un clan nuevo pasa a ser **solo** editar `scraper/config.py`; el bot lo
toma solo en el próximo arranque (los atajos `-grafico<clan>` se registran en el
setup del cog Charts).
"""

from __future__ import annotations

import re

from bot.config import CLAN_NAMES as FALLBACK_CLANS, json_url


def _slug(clan: str, sep: str) -> str:
    """Normaliza un tag de clan a slug: minúsculas y no-alfanuméricos → *sep*.
    Ej. RIM:LA→rim_la / rim-la, FI-R→fi_r / fi-r, E-102→e_102 / e-102."""
    return re.sub(r"[^a-z0-9]", sep, clan.lower())


def grafico_alias(clan: str) -> str:
    """Nombre del atajo de gráfico para un clan (espeja el esquema histórico).
    Ej. RIM:LA→graficorim_la, FI-R→graficofi_r, 300→grafico300."""
    return "grafico" + _slug(clan, "_")


class ClanRegistry:
    """Lista de clanes + resolución case-insensitive y derivados."""

    def __init__(self, tags):
        # Orden estable y sin duplicados.
        self.tags = sorted(dict.fromkeys(t for t in tags if t))
        # Índice de resolución: acepta el tag tal cual, en minúsculas y ambos slugs
        # (guion y guion bajo) para que -top rim-la / rim_la / RIM:LA funcionen.
        self._by_key: dict[str, str] = {}
        for t in self.tags:
            for key in (t.lower(), _slug(t, "-"), _slug(t, "_")):
                self._by_key.setdefault(key, t)

    def resolve(self, name: str | None) -> str | None:
        """Devuelve el tag canónico para *name* (tolera mayúsculas/slugs) o None."""
        if not name:
            return None
        return (
            self._by_key.get(name.lower())
            or self._by_key.get(_slug(name, "-"))
            or self._by_key.get(_slug(name, "_"))
        )

    def top_categories(self) -> dict[str, str | None]:
        """{clave_lower: tag | None}. Incluye 'general'→None (ranking global)."""
        cats: dict[str, str | None] = {"general": None}
        for t in self.tags:
            cats[t.lower()] = t
            cats[_slug(t, "-")] = t
        return cats

    @staticmethod
    def json_url(clan: str) -> str:
        return json_url(clan)

    @classmethod
    def from_averages(cls, averages) -> "ClanRegistry":
        """Construye el registro desde clan_averages.json (lista de dicts con
        clave 'Clan'). Cae a la lista bundled si viene vacío/roto."""
        tags = []
        if isinstance(averages, list):
            tags = [r.get("Clan") for r in averages if isinstance(r, dict) and r.get("Clan")]
        return cls(tags or FALLBACK_CLANS)


def clan_choices(client, current, extra=()):
    """Helper compartido de autocomplete: devuelve hasta 25 Choice de clanes
    (bot.clans) filtrados por *current*, con *extra* opciones primero (p.ej.
    'general' para -top, o 'all'/'todos' para -grafico). Discord limita a 25 y
    hoy hay >25 clanes, por eso usamos autocomplete en vez de choices estáticos."""
    from discord import app_commands

    reg = getattr(client, "clans", None)
    tags = list(extra) + (reg.tags if reg else [])
    cur = (current or "").lower()
    filtered = [c for c in tags if cur in c.lower()] if cur else tags
    return [app_commands.Choice(name=c, value=c) for c in filtered[:25]]
