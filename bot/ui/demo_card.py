"""Detalles de demos de un jugador en Components V2 (reemplaza el embed de 9 campos
en columnas de DemoDetailsView).

Bloques de lectura vertical — Combate, Supervivencia, Revives, Teamwork,
Disciplina — con barras donde hay un porcentaje, y los tops (kits, armas,
vehículos) como listas cortas. Lo usan el botón "Demos <jugador>" y la pestaña
"Resumen demos" del perfil.
"""

from __future__ import annotations

import discord

from bot.assets.kit_mapping import (
    get_kit_emoji, normalize_kits, weapon_model_name, is_personal_weapon,
    kit_usage, weapon_vehicle_name, is_vehicle_kill,
)
from bot.config import BOT_THUMBNAIL
from bot.ui.theme import accent_meter, ACCENT, last_seen
from bot.utils import format_number


def _group(raw: dict, namer, exclude=None) -> list[tuple[str, int]]:
    out: dict[str, int] = {}
    for code, cnt in (raw or {}).items():
        if exclude and exclude(code):
            continue
        name = namer(code)
        out[name] = out.get(name, 0) + cnt
    return sorted(out.items(), key=lambda kv: kv[1], reverse=True)


def _f2(v) -> str:
    return f"{v:.2f}".replace(".", ",")


def _dur(seconds: float) -> str:
    return f"{seconds / 60:.1f} min".replace(".", ",") if seconds >= 60 else f"{seconds:.0f} s"


def demo_items(d: dict) -> list[discord.ui.Item]:
    """Bloques de la tarjeta (sin encabezado), para reusarlos en el perfil."""
    rounds = d.get("rounds_played", 0) or 0
    tk, td = d.get("total_kills", 0) or 0, d.get("total_deaths", 0) or 0
    blocks = []

    combat = [f"**Combate** · K/D `{_f2(tk / max(td, 1))}` ({format_number(tk)}/{format_number(td)})"]
    extras = []
    if d.get("best_killstreak"):
        extras.append(f"mejor racha `{d['best_killstreak']}`")
    if d.get("total_clutch_kills"):
        extras.append(f"clutch `{d['total_clutch_kills']}`")
    if d.get("total_first_bloods"):
        extras.append(f"first blood `{d['total_first_bloods']}`")
    if extras:
        combat.append("-# " + " · ".join(extras))
    blocks.append("\n".join(combat))

    alive, played, lives = d.get("alive_seconds", 0) or 0, d.get("played_seconds", 0) or 0, d.get("lives", 0) or 0
    if alive and played:
        pct = alive / played
        surv = [f"**Supervivencia** {accent_meter(pct)} `{pct * 100:.0f}%` del tiempo vivo"]
        sub = []
        if lives:
            sub.append(f"vida promedio `{_dur(alive / lives)}`")
        sub.append(f"`{_f2(tk / (alive / 60))}` kills/min vivo")
        surv.append("-# " + " · ".join(sub))
        blocks.append("\n".join(surv))

    rg, rr = d.get("total_revives_given", 0) or 0, d.get("total_revives_received", 0) or 0
    if rg or rr:
        medic = d.get("rounds_as_medic", 0) or 0
        per = f"`{_f2(rg / medic)}` por ronda de médico" if medic else f"`{_f2(rg / max(rounds, 1))}` por ronda"
        blocks.append(f"**Revives** · dados `{rg}` · recibidos `{rr}`\n-# {per}")

    ris, rws = d.get("rounds_in_squad", 0) or 0, d.get("rounds_with_squad_data", 0) or 0
    tw, vd = d.get("total_teamwork_score", 0) or 0, d.get("total_vehicles_destroyed", 0) or 0
    team = []
    if rws:
        team.append(f"**Teamwork** {accent_meter(ris / rws)} `{ris / rws * 100:.0f}%` de rondas en escuadra")
    elif tw or vd:
        team.append("**Teamwork**")
    sub = []
    if tw:
        sub.append(f"score `{format_number(tw)}`")
    if vd:
        sub.append(f"vehículos destruidos `{vd}`")
    if sub:
        team.append("-# " + " · ".join(sub))
    if team:
        blocks.append("\n".join(team))

    tkill, sui = d.get("total_teamkills", 0) or 0, d.get("total_suicides_demo", 0) or 0
    if tkill or sui:
        blocks.append(f"**Disciplina** · teamkills `{tkill}` · suicidios `{sui}`")

    tops = []
    kits = sorted(normalize_kits(kit_usage(d)).items(), key=lambda kv: kv[1], reverse=True)[:3]
    if kits:
        tops.append("**Kits** · " + " · ".join(
            f"{(get_kit_emoji(k) + ' ') if get_kit_emoji(k) else ''}{k} `{c}`" for k, c in kits))
    weapons = _group(d.get("kill_weapons", {}), weapon_model_name, exclude=lambda c: not is_personal_weapon(c))[:3]
    if weapons:
        tops.append("**Armas** · " + " · ".join(f"{w} `{c}`" for w, c in weapons))
    # Por el arma que hizo la baja: `vehicle_kills` sumaba kills a pie hechas después
    # de bajarse (o de morir adentro) del vehículo.
    vehicles = _group(d.get("kill_weapons", {}), weapon_vehicle_name,
                      exclude=lambda c: not is_vehicle_kill(c))[:3]
    if vehicles:
        tops.append("**Vehículos** · " + " · ".join(f"{v} `{c}`" for v, c in vehicles))

    items: list[discord.ui.Item] = [discord.ui.TextDisplay("\n\n".join(blocks))]
    if tops:
        items += [discord.ui.Separator(), discord.ui.TextDisplay("### Más usados\n" + "\n".join(tops))]
    items.append(discord.ui.TextDisplay(f"-# {last_seen(d)} · de {rounds} rondas con demo"))
    return items


class DemoCard(discord.ui.LayoutView):
    def __init__(self, d: dict):
        super().__init__(timeout=None)
        name = d.get("ign", "?")
        head = discord.ui.Section(
            f"## Detalles de demos · {name}",
            f"{format_number(d.get('rounds_played', 0))} rondas · {d.get('wins', 0)}–{d.get('losses', 0)} en victorias",
            accessory=discord.ui.Thumbnail(BOT_THUMBNAIL),
        )
        self.add_item(discord.ui.Container(head, discord.ui.Separator(), *demo_items(d), accent_colour=ACCENT))
