"""Performance Score v3 — percentile-rank scoring with demo integration.

Components (7, all players have demo data):
  20% Combat (K/D)              — percentile rank
  15% Effectiveness (KPR)       — percentile rank
  10% Score Contribution (SPR)  — percentile rank
  20% Winrate (demos)           — absolute normalization
  15% Teamwork (demos)          — absolute normalization
  10% Consistency (demos)       — absolute normalization
  10% Experience (rounds)       — log scale

Radar: 6 axes (Letalidad, Supervivencia, Teamwork, Impacto, Consistencia, Versatilidad)
Ratings: 4 composite indices (Combat, Tactical, Reliability, Impact) 0-100
Archetypes: 11 types (kit-based > stat-pattern > fallback)
Tiers: dynamic percentile-based (Elite ~5%, Veterano ~20%, Experimentado ~35%, Soldado ~30%, Recluta ~10%)
"""

import json
import logging
import math
import os

import pandas as pd

from .config import (
    DEMOS_DIR,
    NORM_CAPS,
    LOW_ROUNDS_THRESHOLD,
    MIN_ROUNDS_PENALTY,
    MEDIC_KITS,
    OFFICER_KITS,
    ARMOR_KITS,
    AT_KITS,
)

logger = logging.getLogger(__name__)

# ── v3 component weights (sum = 1.0) ────────────────────────────────────────
W_COMBAT = 0.20
W_EFFECTIVENESS = 0.15
W_SCORE = 0.10
W_WINRATE = 0.20
W_TEAMWORK = 0.15
W_CONSISTENCY = 0.10
W_EXPERIENCE = 0.10

# Neutral value for missing demo components
NEUTRAL = 0.5


# ── Helpers ──────────────────────────────────────────────────────────────────

def _sigmoid_penalty(rounds: float) -> float:
    """Smooth sigmoid penalty for low round counts.

    Centered at 25 rounds, slope controlled by divisor 10.
    Players with very few rounds get penalized; those above ~50 are near 1.0.
    """
    return 1.0 / (1.0 + math.exp(-((rounds - 25) / 10)))


def _activity_index(rounds: int, kd: float, score_per_round: float, kills_per_round: float) -> float:
    """Calculate an Activity Index (0-100) combining volume and engagement."""
    volume = min(math.log(max(rounds, 1) + 1) / math.log(1001), 1.0)
    engagement = min(score_per_round / 500.0, 1.0)
    impact = min(kills_per_round / 10.0, 1.0)
    index = (0.40 * volume + 0.30 * engagement + 0.30 * impact) * 100.0
    return round(index, 1)


def _sanitize_demo_data(demo: dict) -> dict:
    """Clamp demo values to valid ranges."""
    demo = dict(demo)
    if "teamwork_ratio" in demo:
        demo["teamwork_ratio"] = max(0.0, min(demo["teamwork_ratio"], 1.0))
    if "consistency_score" in demo:
        cs = demo["consistency_score"]
        if cs != -1:
            demo["consistency_score"] = max(0, min(cs, 100))
    return demo


def _dynamic_kd_cap(kd: float, rounds: int) -> float:
    """Cap K/D dynamically for low-round players to avoid outliers."""
    cap = 3.0 + (rounds / 100) * 2.0  # At 100 rounds cap is 5.0
    return min(kd, cap)


def _hhi(kits_used: dict) -> float:
    """Herfindahl-Hirschman Index for kit diversity.

    1.0 = one kit only, ~0 = many kits evenly used.
    """
    total = sum(kits_used.values())
    if total == 0:
        return 1.0
    shares = [count / total for count in kits_used.values()]
    return sum(s ** 2 for s in shares)


def _main_role(kits_used: dict, role_kits: list, threshold: float = 0.25) -> bool:
    """Check if a player mainly uses kits from a given role."""
    total = sum(kits_used.values())
    if total == 0:
        return False
    role_count = sum(kits_used.get(k, 0) for k in role_kits)
    return (role_count / total) >= threshold


# ── Demo data loading ────────────────────────────────────────────────────────

def _load_demo_lookup() -> dict:
    """Load demo player_details.json and build {ign_lower: player_dict} lookup."""
    path = os.path.join(DEMOS_DIR, "player_details.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
        return {p.get("ign", "").lower(): p for p in data if p.get("ign")}
    except Exception as e:
        logger.warning("Failed to load demo data for scoring: %s", e)
        return {}


def _get_demo_for_player(name: str, demo_lookup: dict) -> dict | None:
    """Find demo data for a player by name (exact or substring match)."""
    name_lower = name.lower()
    if name_lower in demo_lookup:
        return demo_lookup[name_lower]
    for ign, data in demo_lookup.items():
        if name_lower in ign or ign in name_lower:
            return data
    return None


# ── Performance Score v3 ─────────────────────────────────────────────────────

def _compute_ps_v3(
    kd: float, kpr: float, spr: float, rounds: int,
    demo: dict | None,
    kd_pct: float, kpr_pct: float, spr_pct: float,
) -> float:
    """Compute Performance Score v3 for a single player.

    PRStats components use percentile rank (0-1).
    Demo components use absolute normalization.
    """
    if rounds < MIN_ROUNDS_PENALTY:
        return 0.05

    # PRStats components (percentile rank)
    combat = kd_pct * W_COMBAT
    effectiveness = kpr_pct * W_EFFECTIVENESS
    score_c = spr_pct * W_SCORE
    experience = min(math.log(max(rounds, 1) + 1) / math.log(1001), 1.0) * W_EXPERIENCE

    # Demo components (absolute normalization)
    if demo and demo.get("rounds_played", 0) >= 5:
        demo = _sanitize_demo_data(demo)
        w, l = demo.get("wins", 0), demo.get("losses", 0)
        wr = w / (w + l) if (w + l) >= 5 else 0.5
        winrate = min(max(wr - 0.35, 0) / 0.30, 1.0) * W_WINRATE

        tw = demo.get("teamwork_ratio", 0)
        if tw == 0:
            ts = demo.get("total_score", 0)
            tws = demo.get("total_teamwork_score", 0)
            tw = tws / ts if ts > 0 else 0
            tw = max(0.0, min(tw, 1.0))
        teamwork = min(tw / 0.60, 1.0) * W_TEAMWORK

        cons = demo.get("consistency_score", 50)
        if cons < 0:
            cons = 50
        consistency = (cons / 100.0) * W_CONSISTENCY
    else:
        winrate = NEUTRAL * W_WINRATE
        teamwork = NEUTRAL * W_TEAMWORK
        consistency = NEUTRAL * W_CONSISTENCY

    raw = combat + effectiveness + score_c + winrate + teamwork + consistency + experience
    return round(raw * _sigmoid_penalty(rounds), 4)


# ── Radar (6 axes) ───────────────────────────────────────────────────────────

def _compute_radar(
    kd_pct: float, kpr_pct: float, dpr: float, p95_dpr: float,
    demo: dict | None, ps: float, rounds: int,
) -> dict:
    """Compute 6-axis radar profile, all values clamped [0, 1]."""
    # Letalidad
    letalidad = kpr_pct

    # Supervivencia: 60% K/D percentile + 40% inverse DPR
    inv_dpr = max(1 - dpr / p95_dpr, 0) if p95_dpr > 0 else 0.5
    supervivencia = 0.6 * kd_pct + 0.4 * inv_dpr

    if demo and demo.get("rounds_played", 0) >= 5:
        demo = _sanitize_demo_data(demo)
        # Teamwork
        tw = demo.get("teamwork_ratio", 0)
        rp = demo.get("rounds_played", 1)
        revives_per_round = demo.get("total_revives_given", 0) / max(rp, 1)
        flags_per_round = demo.get("total_flags_captured", 0) / max(rp, 1)
        tw_comp = min(tw / 0.6, 1.0) * 0.5
        rev_comp = min(revives_per_round / 0.8, 1.0) * 0.3
        flag_comp = min(flags_per_round / 0.05, 1.0) * 0.2
        teamwork = tw_comp + rev_comp + flag_comp

        # Impacto
        w, l = demo.get("wins", 0), demo.get("losses", 0)
        wr = w / (w + l) if (w + l) >= 5 else 0.5
        winrate_dev = min(max(wr - 0.5, 0) / 0.25, 1.0)
        ws = demo.get("win_stats", {})
        avg_k_w = ws.get("avg_kills_in_wins", 0)
        avg_k_l = ws.get("avg_kills_in_losses", 0)
        clutch = (avg_k_w - avg_k_l) / max(avg_k_w, 1)
        clutch = max(0, min(clutch, 1.0))
        impacto = winrate_dev * 0.5 + clutch * 0.3 + ps * 0.2

        # Consistencia
        cons = demo.get("consistency_score", 50)
        if cons < 0:
            cons = 50
        sig_rounds = 1.0 / (1.0 + math.exp(-((rounds - 50) / 15)))
        consistencia = (cons / 100.0) * 0.7 + sig_rounds * 0.3

        # Versatilidad
        kits = demo.get("kits_used", {})
        versatilidad = 1 - _hhi(kits) if kits else 0.0
    else:
        teamwork = 0.3
        impacto = ps * 0.5
        consistencia = 0.3
        versatilidad = 0.3

    return {
        "letalidad": round(max(0, min(letalidad, 1.0)), 3),
        "supervivencia": round(max(0, min(supervivencia, 1.0)), 3),
        "teamwork": round(max(0, min(teamwork, 1.0)), 3),
        "impacto": round(max(0, min(impacto, 1.0)), 3),
        "consistencia": round(max(0, min(consistencia, 1.0)), 3),
        "versatilidad": round(max(0, min(versatilidad, 1.0)), 3),
    }


# ── 4 Composite Ratings (0-100) ─────────────────────────────────────────────

def _compute_ratings(
    kd: float, kpr: float, spr: float, dpr: float, rounds: int,
    demo: dict | None,
    p95_kpr: float, p95_spr: float, p95_dpr: float,
) -> dict:
    """Compute 4 composite ratings, each 0-100."""
    penalty = _sigmoid_penalty(rounds)

    # Combat Rating
    combat = (
        0.35 * min(kd / 3.0, 1.0)
        + 0.30 * min(kpr / 7.0, 1.0)
        + 0.20 * (max(1 - dpr / p95_dpr, 0) if p95_dpr > 0 else 0.5)
        + 0.15 * min(spr / 500, 1.0)
    ) * 100 * penalty

    if demo and demo.get("rounds_played", 0) >= 5:
        demo = _sanitize_demo_data(demo)
        rp = demo.get("rounds_played", 1)
        tw = demo.get("teamwork_ratio", 0)
        revives_pr = demo.get("total_revives_given", 0) / max(rp, 1)
        flags_pr = demo.get("total_flags_captured", 0) / max(rp, 1)
        vehicles_pr = demo.get("total_vehicles_destroyed", 0) / max(rp, 1)
        w, l = demo.get("wins", 0), demo.get("losses", 0)
        wr = w / (w + l) if (w + l) >= 5 else 0.5
        wr_norm = min(max(wr - 0.35, 0) / 0.30, 1.0)

        cons = demo.get("consistency_score", 50)
        if cons < 0:
            cons = 50

        longest_loss = demo.get("longest_loss_streak", 0)

        ws = demo.get("win_stats", {})
        avg_k_w = ws.get("avg_kills_in_wins", 0)
        avg_k_l = ws.get("avg_kills_in_losses", 0)
        clutch = max(0, (avg_k_w - avg_k_l) / max(avg_k_w, 1))
        clutch = min(clutch, 1.0)

        best_kills = demo.get("best_round", {}).get("kills", 0)

        # Tactical Rating
        tactical = (
            0.30 * min(tw / 0.6, 1.0)
            + 0.20 * min(revives_pr / 0.8, 1.0)
            + 0.20 * wr_norm
            + 0.15 * min(flags_pr / 0.05, 1.0)
            + 0.15 * min(vehicles_pr / 0.3, 1.0)
        ) * 100 * penalty

        # Reliability Rating (no sigmoid penalty — experience is built in)
        exp_norm = min(math.log(max(rounds, 1) + 1) / math.log(1001), 1.0)
        loss_penalty = 1 - (longest_loss / max(rounds, 1))
        reliability = (
            0.40 * exp_norm
            + 0.35 * (cons / 100.0)
            + 0.25 * max(loss_penalty, 0)
        ) * 100

        # Impact Rating
        winrate_contribution = min(max(wr - 0.5, 0) / 0.25, 1.0)
        impact = (
            0.30 * winrate_contribution
            + 0.25 * clutch
            + (0.20 * min(kpr / p95_kpr, 1.0) if p95_kpr > 0 else 0)
            + (0.15 * min(spr / p95_spr, 1.0) if p95_spr > 0 else 0)
            + 0.10 * min(best_kills / 20, 1.0)
        ) * 100 * penalty
    else:
        tactical = 30.0
        reliability = min(math.log(max(rounds, 1) + 1) / math.log(1001), 1.0) * 40
        impact = 25.0

    return {
        "combat": round(max(0, min(combat, 100)), 1),
        "tactical": round(max(0, min(tactical, 100)), 1),
        "reliability": round(max(0, min(reliability, 100)), 1),
        "impact": round(max(0, min(impact, 100)), 1),
    }


# ── Archetype Classification ────────────────────────────────────────────────

def _classify_archetype(radar: dict, demo: dict | None, rounds: int) -> dict:
    """Classify player archetype based on radar profile and kit usage."""
    # Priority 3 — Fallbacks (check first for early return)
    if rounds < 30:
        return {"name": "Novato", "emoji": "\U0001f331", "desc": "Pocos datos para clasificar"}

    # Priority 1 — Kit-based (from demo data)
    if demo and demo.get("rounds_played", 0) >= 5:
        kits = demo.get("kits_used", {})
        tw = radar.get("teamwork", 0)
        imp = radar.get("impacto", 0)

        if _main_role(kits, MEDIC_KITS, 0.30) and tw > 0.6:
            return {"name": "Médico", "emoji": "\U0001fa79", "desc": "Soporte de equipo, prioriza curar y revivir"}
        if _main_role(kits, OFFICER_KITS, 0.20) and tw > 0.5 and imp > 0.5:
            return {"name": "Oficial", "emoji": "\U0001f4e1", "desc": "Liderazgo y coordinación táctica"}
        if _main_role(kits, ARMOR_KITS, 0.25):
            return {"name": "Tanquista", "emoji": "\U0001f6e1\ufe0f", "desc": "Especialista en vehículos blindados"}
        if _main_role(kits, AT_KITS, 0.25):
            return {"name": "Demoledor", "emoji": "\U0001f4a5", "desc": "Anti-tanque y demolición"}

    # Priority 2 — Stat patterns
    let_ = radar.get("letalidad", 0)
    sup = radar.get("supervivencia", 0)
    tw = radar.get("teamwork", 0)
    imp = radar.get("impacto", 0)
    con = radar.get("consistencia", 0)
    ver = radar.get("versatilidad", 0)

    if let_ > 0.6 and sup > 0.7 and (tw == 0 or let_ / max(tw, 0.01) > 2.0):
        return {"name": "Francotirador", "emoji": "\U0001f3af", "desc": "Precisión letal desde la distancia"}
    if let_ > 0.75 and sup < 0.6:
        return {"name": "Asesino", "emoji": "\U0001f5e1\ufe0f", "desc": "Altamente letal pero arriesgado"}
    if sup > 0.8 and let_ < 0.5:
        return {"name": "Superviviente", "emoji": "\U0001f6e1\ufe0f", "desc": "Difícil de eliminar, juega seguro"}
    if let_ > 0.7 and imp > 0.7 and con > 0.5:
        return {"name": "Tanque", "emoji": "\U0001f3cb\ufe0f", "desc": "Domina el combate con consistencia"}
    if con > 0.7 and all(radar.get(a, 0) >= 0.4 for a in ("letalidad", "supervivencia", "teamwork", "impacto")) and ver > 0.5:
        return {"name": "Veterano", "emoji": "\u2b50", "desc": "Rendimiento sólido y versátil"}

    # Priority 3 — Default
    return {"name": "Soldado", "emoji": "\u2694\ufe0f", "desc": "Combatiente de infantería estándar"}


# ── Tier Thresholds ──────────────────────────────────────────────────────────

def compute_tier_thresholds(df: pd.DataFrame) -> dict:
    """Compute dynamic tier thresholds from the PS distribution.

    Only considers players with rounds >= LOW_ROUNDS_THRESHOLD.
    Returns dict with threshold values for each tier boundary.
    """
    eligible = df[df["Rounds"] >= LOW_ROUNDS_THRESHOLD]["Performance Score"]
    if eligible.empty:
        return {"elite": 0.70, "veterano": 0.55, "experimentado": 0.40, "soldado": 0.25}
    return {
        "elite": float(eligible.quantile(0.95)),
        "veterano": float(eligible.quantile(0.75)),
        "experimentado": float(eligible.quantile(0.40)),
        "soldado": float(eligible.quantile(0.10)),
    }


# ── Main entry point ────────────────────────────────────────────────────────

def calculate_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate Performance Score v3, Activity Index, radar, ratings, and archetypes.

    Expected input columns: K/D Ratio, Score per Round, Kills per Round, Rounds, Player,
                            Total Deaths.
    """
    if df.empty:
        logger.warning("Empty DataFrame passed to calculate_scores.")
        return df

    df = df.copy()

    # Load demo data
    demo_lookup = _load_demo_lookup()
    demo_count = 0

    # Apply dynamic K/D cap
    df["_effective_kd"] = df.apply(
        lambda r: _dynamic_kd_cap(r["K/D Ratio"], int(r["Rounds"])), axis=1,
    )

    # Percentile ranks for PRStats (using effective K/D)
    df["_kd_pct"] = df["_effective_kd"].rank(pct=True)
    df["_kpr_pct"] = df["Kills per Round"].rank(pct=True)
    df["_spr_pct"] = df["Score per Round"].rank(pct=True)

    # Fixed-range normalization (kept for backward compatibility)
    df["Normalized_KD"] = (df["K/D Ratio"] / NORM_CAPS["kd"]).clip(upper=1.0)
    df["Normalized_Score"] = (df["Score per Round"] / NORM_CAPS["score_per_round"]).clip(upper=1.0)
    df["Normalized_Kills_Per_Round"] = (df["Kills per Round"] / NORM_CAPS["kills_per_round"]).clip(upper=1.0)
    df["Normalized_Rounds"] = (df["Rounds"] / NORM_CAPS["rounds"]).clip(upper=1.0)

    # Deaths per Round
    df["Deaths per Round"] = df["Total Deaths"] / df["Rounds"]

    # P95 reference values for ratings/radar
    p95_kpr = float(df["Kills per Round"].quantile(0.95)) if len(df) > 10 else 7.0
    p95_spr = float(df["Score per Round"].quantile(0.95)) if len(df) > 10 else 500.0
    p95_dpr = float(df["Deaths per Round"].quantile(0.95)) if len(df) > 10 else 6.0

    # Activity Index (0-100)
    df["Activity Index"] = df.apply(
        lambda r: _activity_index(int(r["Rounds"]), r["K/D Ratio"], r["Score per Round"], r["Kills per Round"]),
        axis=1,
    )

    # Performance Score v3
    ps_list = []
    radar_list = []
    ratings_list = []
    archetype_list = []

    for _, row in df.iterrows():
        demo = _get_demo_for_player(row["Player"], demo_lookup)
        if demo:
            demo_count += 1

        kd = row["K/D Ratio"]
        kpr = row["Kills per Round"]
        spr = row["Score per Round"]
        rounds = int(row["Rounds"])
        dpr = row["Deaths per Round"]

        ps = _compute_ps_v3(
            kd, kpr, spr, rounds, demo,
            row["_kd_pct"], row["_kpr_pct"], row["_spr_pct"],
        )
        ps_list.append(ps)

        radar = _compute_radar(
            row["_kd_pct"], row["_kpr_pct"], dpr, p95_dpr,
            demo, ps, rounds,
        )
        radar_list.append(radar)

        ratings = _compute_ratings(
            kd, kpr, spr, dpr, rounds, demo,
            p95_kpr, p95_spr, p95_dpr,
        )
        ratings_list.append(ratings)

        archetype = _classify_archetype(radar, demo, rounds)
        archetype_list.append(archetype)

    df["Performance Score"] = ps_list
    df["radar"] = radar_list
    df["ratings"] = ratings_list
    df["archetype"] = archetype_list

    # Clean up temp columns
    df.drop(columns=["_effective_kd", "_kd_pct", "_kpr_pct", "_spr_pct"], inplace=True)

    logger.info(
        "v3 scores calculated for %d players (%d with demo data). PS range: %.4f—%.4f, AI range: %.1f—%.1f",
        len(df),
        demo_count,
        df["Performance Score"].min(),
        df["Performance Score"].max(),
        df["Activity Index"].min(),
        df["Activity Index"].max(),
    )

    return df
