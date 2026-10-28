"""Estadísticas por rol y tops por rol (médicos, anti-tanques, tripulantes…).

El rol de cada kill y cada muerte sale del kit que el jugador tenía puesto en ese
momento (`kit_kills` / `kit_deaths` de cada ronda). `kits_used` no sirve para esto:
cuenta también los kits que se miran en el menú antes de reaparecer y los que se
levantan del piso, así que casi todos salían "médicos".

Cada rol se mide por lo que le toca hacer (revives para el médico, kills con lanzador
para el AT…) y se compara solo con otros jugadores de ese rol. Para que una ronda
excepcional no defina a nadie:
  - el valor se ajusta por muestra (con pocas rondas o muertes se acerca a la mediana
    del rol);
  - la confianza es baja con menos de 8 rondas o si una sola ronda explica más del
    40 % del resultado, y con confianza baja no se entra al top ni se es "mejor rol".

Las rondas viejas sin dato de kit quedan afuera del cálculo.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from statistics import median

from .aliases import resolve_kit, resolve_weapon
from .config import DEMOS_DIR
from .rounds_store import ClanMatcher, _round_dt, round_time_per_tick

logger = logging.getLogger(__name__)

ROLE_LEADERBOARDS_PATH = os.path.join(DEMOS_DIR, "role_leaderboards.json")

# Métricas: "kd" (K/D con ese kit), "winrate" (victorias en rondas con ese rol) o una
# tasa por ronda (`rate`) cuyo numerador sale de la ronda.
ROLE_BOARDS = [
    {"key": "medico", "label": "Médico", "roles": {"Médico"},
     "metric": "rate", "num": "revives", "metric_label": "Revives por ronda"},
    {"key": "at", "label": "Anti-tanque (LAT/HAT)",
     "roles": {"Anti-tanque ligero", "Anti-tanque pesado"},
     "metric": "rate", "num": "at_kills", "metric_label": "Kills con lanzador AT por ronda"},
    {"key": "tripulante", "label": "Tripulante", "roles": {"Tripulante de vehículo"},
     "metric": "rate", "num": "ground_vehicle_kills", "metric_label": "Kills con armas de vehículo por ronda"},
    {"key": "piloto", "label": "Piloto", "roles": {"Piloto"},
     "metric": "rate", "num": "air_kills", "metric_label": "Kills desde aeronaves por ronda"},
    {"key": "aa", "label": "Antiaéreo", "roles": {"Antiaéreo"},
     "metric": "rate", "num": "aa_kills", "metric_label": "Kills con lanzador AA por ronda"},
    {"key": "fusilero", "label": "Fusilero", "roles": {"Fusilero", "Fusil"},
     "metric": "kd", "metric_label": "K/D con el rol"},
    {"key": "tirador", "label": "Tirador", "roles": {"Francotirador", "Tirador designado"},
     "metric": "kd", "metric_label": "K/D con el rol"},
    {"key": "ametrallador", "label": "Ametrallador", "roles": {"Ametrallador"},
     "metric": "kd", "metric_label": "K/D con el rol"},
    {"key": "ar", "label": "Fusilero automático", "roles": {"Fusilero automático"},
     "metric": "kd", "metric_label": "K/D con el rol"},
    {"key": "granadero", "label": "Granadero", "roles": {"Granadero", "Lanzagranadas"},
     "metric": "kd", "metric_label": "K/D con el rol"},
    {"key": "breacher", "label": "Breacher", "roles": {"Breacher"},
     "metric": "kd", "metric_label": "K/D con el rol"},
    {"key": "ingeniero", "label": "Ingeniero de combate", "roles": {"Ingeniero de combate", "Zapador"},
     "metric": "kd", "metric_label": "K/D con el rol"},
    {"key": "oficial", "label": "Oficial", "roles": {"Oficial"},
     "metric": "winrate", "metric_label": "Victorias con el rol"},
    {"key": "observador", "label": "Observador", "roles": {"Observador"},
     "metric": "kd", "metric_label": "K/D con el rol"},
]
_BOARD_BY_ROLE = {role: b["key"] for b in ROLE_BOARDS for role in b["roles"]}
_BOARDS = {b["key"]: b for b in ROLE_BOARDS}

MIN_ROUNDS_POPULATION = 5   # para entrar en la mediana y el percentil del rol
MIN_ROUNDS_TOP = 10         # para entrar al top
PRIOR_DEATHS = 20           # ajuste del K/D: "muertes" a la mediana que se suman
PRIOR_ROUNDS = 10           # ajuste de tasas y winrate: rondas a la mediana que se suman
MAX_BEST_ROUND_SHARE = 0.40  # más que esto de una sola ronda → confianza baja
TOP_SIZE = 30
_PERIODS = {"todo": 0, "mes": 30}


@lru_cache(maxsize=None)
def _board_of_kit(kit: str):
    return _BOARD_BY_ROLE.get(resolve_kit(kit))


@lru_cache(maxsize=None)
def _weapon_class(code: str) -> str:
    """'at', 'aa', 'ground', 'air' o '' según el arma que hizo la baja."""
    w = resolve_weapon(code)
    if w.get("kind") == "AT":
        return "at"
    if w.get("kind") == "AA":
        return "aa"
    if w.get("kind") == "vehicle" and w.get("vclass") == "vehicle":
        return "air" if w.get("vtype") == "air" else "ground"
    return ""


def _new_acc() -> dict:
    return {"rounds": 0, "kills": 0, "deaths": 0, "wins": 0, "losses": 0,
            "num": 0, "per_round": [], "alive_seconds": 0.0}


def _accumulate(rounds: list[dict], matcher: ClanMatcher, cutoff=None) -> dict:
    """{jugador: {board_key: acumulado}} sobre las rondas con dato de kit."""
    out: dict[str, dict[str, dict]] = {}
    for rd in rounds:
        if cutoff is not None:
            dt = _round_dt(rd.get("filename", ""))
            if dt is None or dt < cutoff:
                continue
        winner = rd.get("winner", -1)
        tpt = round_time_per_tick(rd)
        for pdata in rd.get("players", {}).values():
            if "kit_kills" not in pdata and "kit_deaths" not in pdata:
                continue  # ronda vieja, sin kit por evento
            name = matcher.match((pdata.get("ign") or "").strip())
            if name is None:
                continue
            kills = {}
            deaths = {}
            for kit, c in (pdata.get("kit_kills") or {}).items():
                b = _board_of_kit(kit)
                if b:
                    kills[b] = kills.get(b, 0) + c
            for kit, c in (pdata.get("kit_deaths") or {}).items():
                b = _board_of_kit(kit)
                if b:
                    deaths[b] = deaths.get(b, 0) + c
            alive = {}
            for kit, ticks in (pdata.get("kit_alive_ticks") or {}).items():
                b = _board_of_kit(kit)
                if b:
                    alive[b] = alive.get(b, 0.0) + ticks * tpt
            # El rol cuenta en la ronda si mató, murió o estuvo vivo con ese kit. Las
            # revives solas no alcanzan: en ~30 % de las rondas con revives no hay
            # ningún evento con kit médico (casi siempre 1 revive suelta).
            present = set(kills) | set(deaths) | set(alive)
            if not present:
                continue
            revives = pdata.get("revives_given", 0) or 0

            wclass = {"at": 0, "aa": 0, "ground": 0, "air": 0}
            for w, c in (pdata.get("kill_weapons") or {}).items():
                k = _weapon_class(w)
                if k:
                    wclass[k] += c
            nums = {"revives": revives, "at_kills": wclass["at"], "aa_kills": wclass["aa"],
                    "ground_vehicle_kills": wclass["ground"], "air_kills": wclass["air"]}
            team = pdata.get("team", -1)
            decided = winner in (1, 2) and team in (1, 2)
            prow = out.setdefault(name, {})
            for b in present:
                a = prow.setdefault(b, _new_acc())
                board = _BOARDS[b]
                k, d = kills.get(b, 0), deaths.get(b, 0)
                a["rounds"] += 1
                a["kills"] += k
                a["deaths"] += d
                a["alive_seconds"] += alive.get(b, 0.0)
                if decided:
                    a["wins" if winner == team else "losses"] += 1
                if board["metric"] == "rate":
                    n = nums[board["num"]]
                    a["num"] += n
                    a["per_round"].append(n)
                elif board["metric"] == "kd":
                    a["per_round"].append(k)
    return out


def _raw(board: dict, a: dict):
    if board["metric"] == "kd":
        return a["kills"] / max(a["deaths"], 1)
    if board["metric"] == "winrate":
        g = a["wins"] + a["losses"]
        return a["wins"] / g if g else None
    return a["num"] / a["rounds"] if a["rounds"] else None


def _adjusted(board: dict, a: dict, med: float):
    if board["metric"] == "kd":
        return (a["kills"] + PRIOR_DEATHS * med) / (a["deaths"] + PRIOR_DEATHS)
    if board["metric"] == "winrate":
        return (a["wins"] + PRIOR_ROUNDS * med) / (a["wins"] + a["losses"] + PRIOR_ROUNDS)
    return (a["num"] + PRIOR_ROUNDS * med) / (a["rounds"] + PRIOR_ROUNDS)


def _best_share(a: dict):
    total = sum(a["per_round"])
    return round(max(a["per_round"]) / total, 3) if total > 0 else None


def _confidence(a: dict, share) -> str:
    if a["rounds"] < 8 or (share is not None and share > MAX_BEST_ROUND_SHARE):
        return "baja"
    return "alta" if a["rounds"] >= 15 else "media"


def _finalize(acc: dict) -> dict:
    """{jugador: {board_key: entrada}} con valor ajustado, percentil y confianza."""
    result: dict[str, dict] = {name: {} for name in acc}
    for b in ROLE_BOARDS:
        key = b["key"]
        rows = [(n, roles[key]) for n, roles in acc.items() if key in roles]
        pop = [a for _, a in rows if a["rounds"] >= MIN_ROUNDS_POPULATION]
        raws = [r for r in (_raw(b, a) for a in pop) if r is not None]
        med = median(raws) if raws else (0.5 if b["metric"] == "winrate" else 0.0)
        pop_adj = sorted(_adjusted(b, a, med) for a in pop)
        for name, a in rows:
            raw = _raw(b, a)
            if raw is None:
                continue
            adj = _adjusted(b, a, med)
            below = sum(1 for v in pop_adj if v < adj)
            share = _best_share(a)
            conf = _confidence(a, share)
            result[name][key] = {
                "key": key, "label": b["label"], "metric": b["metric"],
                "metric_label": b["metric_label"],
                "rounds": a["rounds"], "kills": a["kills"], "deaths": a["deaths"],
                "wins": a["wins"], "losses": a["losses"],
                "value": round(raw, 3), "adjusted": round(adj, 3), "median": round(med, 3),
                "pct": round(below / len(pop_adj), 3) if pop_adj else None,
                "population": len(pop_adj),
                "best_round_share": share, "confidence": conf,
                "eligible": a["rounds"] >= MIN_ROUNDS_TOP and conf != "baja",
                "alive_seconds": round(a["alive_seconds"], 1),
            }
    return result


def _player_roles(fin: dict) -> dict:
    """{jugador: {"roles": [...], "best_role": key|None}} a partir de `_finalize`.

    `roles` va ordenado por actividad (kills + muertes con el rol) y trae `share`,
    la parte de la actividad del jugador que pasó con ese rol."""
    out = {}
    for name, roles in fin.items():
        entries = list(roles.values())
        total = sum(e["kills"] + e["deaths"] for e in entries) or 1
        for e in entries:
            e["share"] = round((e["kills"] + e["deaths"]) / total, 3)
        entries.sort(key=lambda e: (e["kills"] + e["deaths"], e["rounds"]), reverse=True)
        cands = [e for e in entries if e["confidence"] != "baja" and e["pct"] is not None]
        best = max(cands, key=lambda e: e["pct"])["key"] if cands else None
        out[name] = {"roles": entries, "best_role": best}
    return out


def build_role_leaderboards(rounds: list[dict], clan_player_names: set | None,
                            clan_of: dict | None = None) -> dict:
    """Escribe role_leaderboards.json (top por rol, histórico y últimos 30 días) y
    devuelve los roles de cada jugador sobre todo el historial, para player_details."""
    now = datetime.now(timezone(timedelta(hours=-3)))
    matcher = ClanMatcher(clan_player_names)
    clan_of = clan_of or {}
    payload = {"generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
               "min_rounds": MIN_ROUNDS_TOP, "periods": {}}
    roles_todo = {}
    for period, days in _PERIODS.items():
        cutoff = (now - timedelta(days=days)) if days else None
        fin = _finalize(_accumulate(rounds, matcher, cutoff))
        if not days:
            roles_todo = _player_roles(fin)
        boards = {}
        for b in ROLE_BOARDS:
            entries = [dict(e, player=n, clan=clan_of.get(n, ""))
                       for n, roles in fin.items() if (e := roles.get(b["key"])) and e["eligible"]]
            entries.sort(key=lambda e: e["adjusted"], reverse=True)
            sample = next(iter(r[b["key"]] for r in fin.values() if b["key"] in r), None)
            boards[b["key"]] = {
                "label": b["label"], "metric": b["metric"], "metric_label": b["metric_label"],
                "median": sample["median"] if sample else None,
                "players": [{k: e[k] for k in ("player", "clan", "rounds", "kills", "deaths",
                                               "wins", "losses", "value", "adjusted", "pct",
                                               "confidence")}
                            for e in entries[:TOP_SIZE]],
            }
        payload["periods"][period] = boards
    with open(ROLE_LEADERBOARDS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    logger.info("Saved %s (%s)", ROLE_LEADERBOARDS_PATH, ", ".join(
        f"{k}:{len(v['players'])}" for k, v in payload["periods"]["todo"].items()))
    return roles_todo
