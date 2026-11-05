"""Modelo de fuerza de equipos: el mismo de la web (web/js/squads.js).

Fuerza de un jugador = Performance, K/D y kills por ronda con los pesos de
tier_config.json, cada valor ajustado por muestra hacia la mediana de la
comunidad (n / (n + 50)): con 2 rondas buenas nadie es favorito.
La fuerza del equipo es el promedio de la de sus jugadores; con equipos de
distinto tamaño, el más chico suma menos (los lugares vacíos valen cero).
La probabilidad es una logística sobre la diferencia de fuerza (K = 6).
"""

from __future__ import annotations

import math
from itertools import combinations

from bot.utils import find_player

PRIOR_ROUNDS = 50
PROB_K = 6
MIN_ROUNDS = 50          # para la mediana y para sugerir jugadores
FEW_ROUNDS = 50          # por debajo se avisa que cuenta cerca del promedio
CAPS = {"kd": 5.0, "kpr": 10.0}

# Roles que necesita una escuadra de infantería: (claves de rol de demos, etiqueta).
NEEDED = [(("oficial",), "Oficial"), (("medico",), "Médico"),
          (("ar", "ametrallador"), "AR o MG"), (("at",), "Anti-tanque")]


def weights(tier_config: dict | None) -> dict:
    w = (tier_config or {}).get("predictor_weights") or {}
    t = sum(w.get(k, 0) for k in ("ps", "kd", "kpr"))
    if t > 0:
        return {k: w.get(k, 0) / t for k in ("ps", "kd", "kpr")}
    return {"ps": 0.5, "kd": 0.3, "kpr": 0.2}


class Model:
    def __init__(self, players: list[dict], tier_config: dict | None = None):
        self.players = players or []
        self.w = weights(tier_config)
        pop = [p for p in self.players if (p.get("Rounds") or 0) >= MIN_ROUNDS]

        def med(key):
            v = sorted((p.get(key) or 0) for p in pop)
            return v[len(v) // 2] if v else 0

        self.med = {"Performance Score": med("Performance Score"),
                    "K/D Ratio": med("K/D Ratio"), "Kills per Round": med("Kills per Round")}

    def _shrunk(self, p, key):
        n = p.get("Rounds") or 0
        w = n / (n + PRIOR_ROUNDS)
        return w * (p.get(key) or 0) + (1 - w) * self.med[key]

    def strength(self, p) -> float:
        return (self.w["ps"] * self._shrunk(p, "Performance Score")
                + self.w["kd"] * self._shrunk(p, "K/D Ratio") / CAPS["kd"]
                + self.w["kpr"] * self._shrunk(p, "Kills per Round") / CAPS["kpr"])

    def team_score(self, team) -> float:
        return sum(self.strength(p) for p in team) / len(team) if team else 0.0

    def win_prob(self, a, b, by_size: bool = True) -> float:
        """Probabilidad de que gane `a`."""
        sa, sb = self.team_score(a), self.team_score(b)
        if by_size:
            n = max(len(a), len(b)) or 1
            sa *= len(a) / n
            sb *= len(b) / n
        return 1 / (1 + math.exp(-PROB_K * (sa - sb)))

    def balance(self, players):
        """Dos equipos del mismo tamaño lo más parejos posible (todas las
        combinaciones: con 16 jugadores son 12.870). Devuelve (A, B) o None."""
        n = len(players)
        if n < 2 or n > 16:
            return None
        s = [self.strength(p) for p in players]
        total = sum(s)
        half = n // 2
        big = n - half
        best = None
        for pick in combinations(range(n), half):
            if n % 2 == 0 and pick[0] != 0:
                break  # el primero siempre en A: evita espejos
            sa = sum(s[i] for i in pick)
            d = abs(sa / big - (total - sa) / big)
            if best is None or d < best[0]:
                best = (d, pick)
        chosen = set(best[1])
        return ([players[i] for i in best[1]],
                [p for i, p in enumerate(players) if i not in chosen])


def prob_band(p: float) -> str:
    """Cómo leer la probabilidad del favorito (0,5–1)."""
    p = max(p, 1 - p)
    return ("parejo" if p < 0.55 else "ventaja leve" if p < 0.65
            else "ventaja clara" if p < 0.8 else "muy desbalanceado")


BAND_HELP = "hasta 55 % parejo · 55–65 % ventaja leve · 65–80 % ventaja clara · más de 80 % muy desbalanceado"


def resolve_names(data, names):
    """Busca cada nombre. Devuelve (jugadores, no_encontrados, parciales, repetidos).

    `parciales` son los nombres que se resolvieron por coincidencia parcial
    ("juan" → "juan*ARG*"), para mostrarlos y que nadie juegue con otro sin saberlo.
    """
    found, missing, partial, dups, seen = [], [], [], [], set()
    for raw in names:
        p = find_player(data, raw)
        if not p:
            missing.append(raw)
            continue
        real = p.get("Player", raw)
        if real in seen:
            dups.append(real)
            continue
        seen.add(real)
        if real.lower() != raw.lower():
            partial.append((raw, real))
        found.append(p)
    return found, missing, partial, dups


def split_teams(text: str):
    """Separa "A B vs C D" (acepta vs, VS, contra y |). None si no hay separador."""
    import re
    parts = re.split(r"\s+(?:vs\.?|contra)\s+|\s*\|\s*", text.strip(), maxsplit=1, flags=re.I)
    if len(parts) != 2:
        return None
    return parts[0].split(), parts[1].split()


def roles_text(team, demo_data) -> str:
    """"Juega de" (mejor rol de cada uno) y qué roles de infantería faltan."""
    if not demo_data:
        return ""
    plays: dict[str, int] = {}
    cover: dict[str, int] = {}
    with_demos = 0
    for p in team:
        d = find_player(demo_data, p.get("Player", ""), key="ign")
        if not d or not d.get("rounds_played"):
            continue
        if (d.get("ign") or "").lower() != (p.get("Player") or "").lower():
            continue
        with_demos += 1
        roles = d.get("roles") or []
        best = d.get("best_role")
        if best:
            label = next((r.get("label") for r in roles if r.get("key") == best), best)
            plays[label] = plays.get(label, 0) + 1
        keys = {r.get("key") for r in roles if r.get("eligible") and (r.get("share") or 0) >= 0.1}
        for ks, label in NEEDED:
            if any(k in keys for k in ks):
                cover[label] = cover.get(label, 0) + 1
    if not with_demos:
        return "Sin partidas grabadas: no se pueden ver los roles."
    parts = []
    if plays:
        parts.append("Juega de: " + ", ".join(f"{n}× {lbl}" for lbl, n in sorted(plays.items(), key=lambda x: -x[1])))
    missing = [lbl for _, lbl in NEEDED if not cover.get(lbl)]
    parts.append(("Falta quien cubra: **" + ", ".join(missing) + "**") if missing
                 else "Cubre oficial, médico, AR o MG y anti-tanque")
    line = "\n".join(parts)
    if with_demos < len(team):
        line += f"\n-# {len(team) - with_demos} sin partidas grabadas"
    return line
