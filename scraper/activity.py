"""Actividad real de los jugadores y promedios de clanes "activos".

PRStats solo da totales (sin fechas), así que la actividad se infiere de dos fuentes:

1. **Rondas de PRStats**: cada corrida guarda el total de rondas de cada jugador en
   graphs/activity/rounds_log.json, pero solo cuando cambia (un jugador inactivo
   ocupa una sola entrada). Si sus rondas subieron dentro de la ventana, jugó.
   El primer registro de cada jugador es la línea de base, no cuenta como actividad.
2. **Demos**: ``last_round_date`` de player_details.json (de la corrida anterior).

Activo = cualquiera de las dos dentro de los últimos ``WINDOW_DAYS`` días.

Con eso se arma graphs/clan_averages_active.json: por clan, el promedio de los
``TOP_N`` mejores jugadores activos por Performance Score (clanes con menos de
``MIN_ACTIVE`` activos no entran). El clan_averages.json histórico no cambia.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta

import pandas as pd

from .config import OUTPUT_DIR, DEMOS_DIR

logger = logging.getLogger(__name__)

WINDOW_DAYS = 30
KEEP_DAYS = 45      # historia que se guarda (un poco más que la ventana)
TOP_N = 50
MIN_ACTIVE = 5

ACTIVITY_DIR = os.path.join(OUTPUT_DIR, "activity")
ROUNDS_LOG = os.path.join(ACTIVITY_DIR, "rounds_log.json")
AVERAGE_COLUMNS = [
    "Total Score", "Total Kills", "Total Deaths", "Rounds",
    "Kills per Round", "Score per Round", "Performance Score", "K/D Ratio",
]


def _load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def update_rounds_log(df: pd.DataFrame, today: date) -> dict:
    """Suma el total de rondas de hoy al log (solo si cambió) y lo guarda.

    Formato: {"players": {nombre: [[YYYY-MM-DD, rondas], ...]}}. Se descartan
    entradas viejas, conservando siempre la última anterior al corte como base.
    """
    log = _load_json(ROUNDS_LOG, {})
    players: dict = log.get("players", {}) if isinstance(log, dict) else {}
    today_s = today.isoformat()
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()

    for name, rounds in zip(df["Player"], df["Rounds"]):
        rounds = int(rounds)
        entries = players.setdefault(name, [])
        if not entries or entries[-1][1] != rounds:
            if entries and entries[-1][0] == today_s:
                entries[-1][1] = rounds
            else:
                entries.append([today_s, rounds])
        old = [e for e in entries if e[0] < cutoff]
        recent = [e for e in entries if e[0] >= cutoff]
        players[name] = (old[-1:] + recent) if old else recent

    os.makedirs(ACTIVITY_DIR, exist_ok=True)
    with open(ROUNDS_LOG, "w", encoding="utf-8") as f:
        json.dump({"updated": today_s, "players": players}, f, separators=(",", ":"))
    logger.info("Rounds log: %d jugadores", len(players))
    return players


def _prstats_active(players: dict, today: date) -> set[str]:
    """Jugadores cuyas rondas subieron dentro de la ventana."""
    cutoff = (today - timedelta(days=WINDOW_DAYS)).isoformat()
    active = set()
    for name, entries in players.items():
        for prev, cur in zip(entries, entries[1:]):
            if cur[0] >= cutoff and cur[1] > prev[1]:
                active.add(name)
                break
    return active


def _demo_active(today: date) -> set[str]:
    """Jugadores con una ronda con demo dentro de la ventana (por ign)."""
    details = _load_json(os.path.join(DEMOS_DIR, "player_details.json"), [])
    cutoff = (today - timedelta(days=WINDOW_DAYS)).isoformat()
    return {
        d.get("ign") for d in details
        if isinstance(d, dict) and str(d.get("last_round_date") or "")[:10] >= cutoff
    }


def mark_active(df: pd.DataFrame, today: date | None = None) -> pd.DataFrame:
    """Agrega 'Active 30d' (bool) y 'Active Source' ('prstats'/'demos'/'ambas'/'')."""
    today = today or date.today()
    players = update_rounds_log(df, today)
    by_rounds = _prstats_active(players, today)
    by_demos = _demo_active(today)

    def source(name: str) -> str:
        r, d = name in by_rounds, name in by_demos
        return "ambas" if (r and d) else "prstats" if r else "demos" if d else ""

    df = df.copy()
    df["Active Source"] = df["Player"].map(source)
    df["Active 30d"] = df["Active Source"] != ""
    logger.info("Activos (%d días): %d de %d (PRStats %d, demos %d)", WINDOW_DAYS,
                int(df["Active 30d"].sum()), len(df), len(by_rounds), len(by_demos))
    return df


def clan_averages_active(df: pd.DataFrame) -> pd.DataFrame:
    """Promedio por clan de sus TOP_N mejores jugadores activos (por Performance)."""
    rows = []
    for clan, group in df.groupby("Clan"):
        active = group[group["Active 30d"]].sort_values("Performance Score", ascending=False)
        if len(active) < MIN_ACTIVE:
            continue
        top = active.head(TOP_N)
        row = {"Clan": clan}
        row.update({c: float(top[c].mean()) for c in AVERAGE_COLUMNS})
        row["Active Players"] = int(len(active))
        row["Averaged Players"] = int(len(top))
        row["Total Players"] = int(len(group))
        rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("Performance Score", ascending=False).reset_index(drop=True)
    return out


def write_active_averages(df: pd.DataFrame, timestamp: str) -> None:
    out = clan_averages_active(df)
    path = os.path.join(OUTPUT_DIR, "clan_averages_active.json")
    payload = {
        "generated_at": timestamp,
        "window_days": WINDOW_DAYS,
        "top_n": TOP_N,
        "min_active": MIN_ACTIVE,
        "clans": json.loads(out.to_json(orient="records")) if not out.empty else [],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    logger.info("Saved %s (%d clanes con >= %d activos)", path, len(payload["clans"]), MIN_ACTIVE)
