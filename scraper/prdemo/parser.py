"""High-level PRDemo parser that extracts aggregated statistics.

Processes a .PRdemo file and produces per-player and per-round statistics
including kills, deaths, kits, vehicles, revives, flags, etc.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .decode import DemoReader, RawMessage
from .messages import (
    MESSAGE_DECODERS,
    ServerDetails,
    PlayerAdd,
    PlayerRemove,
    PlayerUpdate,
    Kill,
    Revive,
    KitAllocated,
    VehicleAdd,
    VehicleDestroyed,
    FlagUpdate,
    RoundEnd,
    Ticks,
    Tickets,
)
from .types import MessageType

logger = logging.getLogger(__name__)


@dataclass
class PlayerStats:
    """Aggregated stats for a single player in a round."""

    ign: str = ""
    player_id: int = 0
    team: int = -1
    kills: int = 0
    deaths: int = 0
    score: int = 0
    teamwork_score: int = 0
    revives_given: int = 0
    revives_received: int = 0
    kits_used: Dict[str, int] = field(default_factory=dict)  # kit_name -> veces que cambió a ese kit (≈ pickups)
    vehicle_kills: Dict[str, int] = field(default_factory=dict)  # vehicle_name -> kills
    vehicles_destroyed: int = 0
    flags_captured: int = 0
    kill_weapons: Dict[str, int] = field(default_factory=dict)  # weapon -> count
    death_weapons: Dict[str, int] = field(default_factory=dict)  # weapon -> count


@dataclass
class RoundStats:
    """Complete statistics for a parsed round."""

    # Server/map info
    server_name: str = ""
    map_name: str = ""
    gamemode: str = ""
    layer: int = 0
    blufor_team: str = ""
    opfor_team: str = ""
    max_players: int = 0
    map_size: float = 0.0

    # Round outcome
    winner: int = -1  # 1=blufor, 2=opfor
    tickets1_final: int = 0
    tickets2_final: int = 0
    tickets1_start: int = 0
    tickets2_start: int = 0
    duration_ticks: int = 0

    # Per-player stats
    players: Dict[int, PlayerStats] = field(default_factory=dict)

    # Round-level aggregates
    total_kills: int = 0
    total_revives: int = 0
    total_vehicles_destroyed: int = 0
    total_flags_captured: int = 0
    total_teamkills: int = 0   # bajas a compañeros (no cuentan para el marcador)
    total_suicides: int = 0    # atacante == víctima

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "server_name": self.server_name,
            "map_name": self.map_name,
            "gamemode": self.gamemode,
            "layer": self.layer,
            "blufor_team": self.blufor_team,
            "opfor_team": self.opfor_team,
            "max_players": self.max_players,
            "map_size": self.map_size,
            "winner": self.winner,
            "tickets1_final": self.tickets1_final,
            "tickets2_final": self.tickets2_final,
            "tickets1_start": self.tickets1_start,
            "tickets2_start": self.tickets2_start,
            "duration_ticks": self.duration_ticks,
            "total_kills": self.total_kills,
            "total_revives": self.total_revives,
            "total_vehicles_destroyed": self.total_vehicles_destroyed,
            "total_flags_captured": self.total_flags_captured,
            "total_teamkills": self.total_teamkills,
            "total_suicides": self.total_suicides,
            "players": {
                pid: {
                    "ign": ps.ign,
                    "team": ps.team,
                    "kills": ps.kills,
                    "deaths": ps.deaths,
                    "score": ps.score,
                    "teamwork_score": ps.teamwork_score,
                    "revives_given": ps.revives_given,
                    "revives_received": ps.revives_received,
                    "kits_used": ps.kits_used,
                    "vehicle_kills": ps.vehicle_kills,
                    "vehicles_destroyed": ps.vehicles_destroyed,
                    "flags_captured": ps.flags_captured,
                    "kill_weapons": ps.kill_weapons,
                    "death_weapons": ps.death_weapons,
                }
                for pid, ps in self.players.items()
            },
        }


def parse_demo(reader: DemoReader) -> RoundStats:
    """Parse a PRDemo stream and return aggregated round statistics."""
    stats = RoundStats()

    # Track active entities
    player_names: Dict[int, str] = {}  # player_id -> ign
    vehicle_names: Dict[int, str] = {}  # vehicle_id -> name
    player_vehicles: Dict[int, int] = {}  # player_id -> vehicle_id
    last_kit: Dict[int, str] = {}  # player_id -> último kit conocido (para contar solo cambios)
    flag_owners: Dict[int, int] = {}  # cp_id -> team
    total_ticks = 0
    tickets1_latest = 0
    tickets2_latest = 0

    def get_player(pid: int) -> PlayerStats:
        if pid not in stats.players:
            stats.players[pid] = PlayerStats(
                player_id=pid,
                ign=player_names.get(pid, f"Player_{pid}"),
            )
        return stats.players[pid]

    for raw_msg in reader:
        decoder = MESSAGE_DECODERS.get(raw_msg.msg_type)
        if decoder is None:
            continue

        try:
            decoded = decoder(raw_msg.reader)
        except (EOFError, Exception) as e:
            logger.debug("Failed to decode %s: %s", raw_msg.msg_type.name, e)
            continue

        # ── Server Details ───────────────────────────────────────────
        if raw_msg.msg_type == MessageType.SERVER_DETAILS:
            sd: ServerDetails = decoded
            stats.server_name = sd.server_name
            stats.map_name = sd.map.name
            stats.gamemode = sd.map.gamemode
            stats.layer = sd.map.layer
            stats.blufor_team = sd.blufor_team
            stats.opfor_team = sd.opfor_team
            stats.max_players = sd.max_players
            stats.map_size = sd.map_size
            stats.tickets1_start = sd.tickets1
            stats.tickets2_start = sd.tickets2

        # ── Player Add ───────────────────────────────────────────────
        elif raw_msg.msg_type == MessageType.PLAYER_ADD:
            for pa in decoded:
                player_names[pa.id] = pa.ign
                ps = get_player(pa.id)
                ps.ign = pa.ign

        # ── Player Remove ────────────────────────────────────────────
        elif raw_msg.msg_type == MessageType.PLAYER_REMOVE:
            pr: PlayerRemove = decoded
            player_vehicles.pop(pr.id, None)

        # ── Player Update ────────────────────────────────────────────
        elif raw_msg.msg_type == MessageType.PLAYER_UPDATE:
            for pu in decoded:
                ps = get_player(pu.id)
                if pu.team is not None:
                    ps.team = pu.team
                if pu.kills is not None:
                    ps.kills = pu.kills
                if pu.deaths is not None:
                    ps.deaths = pu.deaths
                if pu.score is not None:
                    ps.score = pu.score
                if pu.teamwork_score is not None:
                    ps.teamwork_score = pu.teamwork_score
                # Contar solo cuando el kit CAMBIA: PLAYER_UPDATE llega muchas veces
                # por jugador (no es un pickup cada vez) → antes inflaba 2–20x/ronda.
                if pu.kit_name and last_kit.get(pu.id) != pu.kit_name:
                    ps.kits_used[pu.kit_name] = ps.kits_used.get(pu.kit_name, 0) + 1
                    last_kit[pu.id] = pu.kit_name
                if pu.vehicle is not None and pu.vehicle.id >= 0:
                    player_vehicles[pu.id] = pu.vehicle.id

        # ── Kill ─────────────────────────────────────────────────────
        elif raw_msg.msg_type == MessageType.KILL:
            kill: Kill = decoded
            stats.total_kills += 1

            attacker = get_player(kill.attacker_id)
            attacker.kill_weapons[kill.weapon] = attacker.kill_weapons.get(kill.weapon, 0) + 1

            # Distinguir suicidio / teamkill: el marcador (total_kills via PLAYER_UPDATE)
            # los excluye, pero el evento KILL los cuenta — de ahí que sum(kill_weapons)
            # supere a total_kills. Los tallamos para poder mostrarlo honesto.
            victim_ps = stats.players.get(kill.victim_id)
            if kill.attacker_id == kill.victim_id:
                stats.total_suicides += 1
            elif (victim_ps is not None and attacker.team != -1
                  and attacker.team == victim_ps.team):
                stats.total_teamkills += 1

            # Track vehicle kills
            if kill.attacker_id in player_vehicles:
                v_id = player_vehicles[kill.attacker_id]
                v_name = vehicle_names.get(v_id, f"Vehicle_{v_id}")
                attacker.vehicle_kills[v_name] = attacker.vehicle_kills.get(v_name, 0) + 1

            victim = get_player(kill.victim_id)
            victim.death_weapons[kill.weapon] = victim.death_weapons.get(kill.weapon, 0) + 1

        # ── Revive ───────────────────────────────────────────────────
        elif raw_msg.msg_type == MessageType.REVIVE:
            rev: Revive = decoded
            stats.total_revives += 1
            get_player(rev.medic_id).revives_given += 1
            get_player(rev.revived_id).revives_received += 1

        # ── Kit Allocated ────────────────────────────────────────────
        elif raw_msg.msg_type == MessageType.KIT_ALLOCATED:
            ka: KitAllocated = decoded
            ps = get_player(ka.player_id)
            # Misma deduplicación que PLAYER_UPDATE: un cambio de kit se cuenta una vez,
            # lo reporte el mensaje que lo reporte (antes se contaba por ambas vías).
            if ka.kit_name and last_kit.get(ka.player_id) != ka.kit_name:
                ps.kits_used[ka.kit_name] = ps.kits_used.get(ka.kit_name, 0) + 1
                last_kit[ka.player_id] = ka.kit_name

        # ── Vehicle Add ──────────────────────────────────────────────
        elif raw_msg.msg_type == MessageType.VEHICLE_ADD:
            for va in decoded:
                vehicle_names[va.id] = va.name

        # ── Vehicle Destroyed ────────────────────────────────────────
        elif raw_msg.msg_type == MessageType.VEHICLE_DESTROYED:
            vd: VehicleDestroyed = decoded
            stats.total_vehicles_destroyed += 1
            if vd.is_killer_known:
                get_player(vd.killer_id).vehicles_destroyed += 1

        # ── Flag Update ──────────────────────────────────────────────
        elif raw_msg.msg_type == MessageType.FLAG_UPDATE:
            fu: FlagUpdate = decoded
            old_owner = flag_owners.get(fu.cp_id, 0)
            flag_owners[fu.cp_id] = fu.owning_team
            if fu.owning_team != old_owner and fu.owning_team != 0:
                stats.total_flags_captured += 1

        # ── Tickets ──────────────────────────────────────────────────
        elif raw_msg.msg_type == MessageType.TICKETS_TEAM1:
            tickets1_latest = decoded.tickets
        elif raw_msg.msg_type == MessageType.TICKETS_TEAM2:
            tickets2_latest = decoded.tickets

        # ── Ticks ────────────────────────────────────────────────────
        elif raw_msg.msg_type == MessageType.TICKS:
            total_ticks += decoded.ticks

        # ── Round End ────────────────────────────────────────────────
        elif raw_msg.msg_type == MessageType.ROUND_END:
            re: RoundEnd = decoded
            stats.winner = re.winner
            stats.tickets1_final = re.tickets1
            stats.tickets2_final = re.tickets2

    # Use latest ticket values if round_end didn't provide them
    if stats.tickets1_final == 0 and tickets1_latest != 0:
        stats.tickets1_final = tickets1_latest
    if stats.tickets2_final == 0 and tickets2_latest != 0:
        stats.tickets2_final = tickets2_latest

    # Infer winner from final tickets if ROUND_END was not present
    if stats.winner == -1:
        t1 = stats.tickets1_final
        t2 = stats.tickets2_final
        if t1 > t2 and t2 >= 0:
            stats.winner = 1  # team 1 (blufor) wins
        elif t2 > t1 and t1 >= 0:
            stats.winner = 2  # team 2 (opfor) wins

    stats.duration_ticks = total_ticks

    return stats


def parse_demo_file(path: str) -> RoundStats:
    """Parse a .PRdemo file from disk and return round statistics."""
    reader = DemoReader.from_file(path)
    return parse_demo(reader)
