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
    SquadName,
    RoundEnd,
    Ticks,
    Tickets,
)
from .types import MessageType

logger = logging.getLogger(__name__)

# Fases temporales para el slider de recorridos (cada ronda se divide en N por
# fracción de duración; fase 0 = apertura … fase N-1 = cierre).
MOVE_PHASES = 6


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
    kit_kills: Dict[str, int] = field(default_factory=dict)   # kit_name -> kills logradas con ese kit
    kit_deaths: Dict[str, int] = field(default_factory=dict)  # kit_name -> muertes sufridas con ese kit
    seat_kills: Dict[str, int] = field(default_factory=dict)  # asiento (gunner/driver/pilot…) -> kills
    vehicles_destroyed_by_type: Dict[str, int] = field(default_factory=dict)  # vehículo destruido -> veces
    squad: int = 0  # escuadra predominante en la ronda (0 = sin escuadra)
    teamkills: int = 0       # bajas a compañeros cometidas por este jugador
    suicides: int = 0        # suicidios de este jugador
    best_killstreak: int = 0  # mayor racha de kills sin morir en la ronda
    first_blood: int = 0     # 1 si logró la primera baja de la ronda
    clutch_kills: int = 0    # bajas con el equipo propio con pocos tickets (<=25)
    alive_ticks: int = 0     # ticks con vida (entre spawn y muerte)
    life_count: int = 0      # vidas completadas (para "vida promedio")
    cohesion_sum: float = 0.0  # suma de distancias al centroide de su escuadra
    cohesion_samples: int = 0  # muestras tomadas (para promediar cohesión)


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
    duration_ticks: int = 0        # cantidad de mensajes TICKS (1 = un frame de demo)
    demo_time_per_tick: float = 0.0  # segundos por tick (de ServerDetails)
    duration_seconds: float = 0.0    # duración real = duration_ticks * demo_time_per_tick

    # Per-player stats
    players: Dict[int, PlayerStats] = field(default_factory=dict)

    # Round-level aggregates
    total_kills: int = 0
    total_revives: int = 0
    total_vehicles_destroyed: int = 0
    total_flags_captured: int = 0
    total_teamkills: int = 0   # bajas a compañeros (no cuentan para el marcador)
    total_suicides: int = 0    # atacante == víctima

    # Nombres de escuadras vistos (clave cruda team_squad → nombre).
    squad_names: Dict[int, str] = field(default_factory=dict)
    # Por kill: [vx, vz, vteam, ax, az, ateam, dist_m, weapon, victim_ign, attacker_ign].
    # ax/az None si el atacante no tiene posición; dist -1 si falta. Sirve para heatmap de
    # muertes (vx,vz,vteam), francotiradores (ax,az,ateam con dist alta y arma personal),
    # líneas de fuego (atacante→víctima) y heatmaps por jugador (igns; solo se capturan).
    kill_positions: List[list] = field(default_factory=list)
    # Eventos de movimiento (rutas): [gx, gy, team, frame] cada vez que alguien entra a
    # una celda nueva. En to_dict se reparten en MOVE_PHASES fases por fracción de ronda
    # (frame/duration) → permite el slider temporal de recorridos.
    move_events: List[list] = field(default_factory=list)
    move_grid_size: int = 128
    # Posiciones de spawn (al revivir): [x, z, equipo].
    spawns: List[list] = field(default_factory=list)
    # Banderas/CPs del FLAG_LIST: [x, z, equipo_dueño, radio]. Para overlay en heatmaps.
    flags: List[list] = field(default_factory=list)

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
            "demo_time_per_tick": self.demo_time_per_tick,
            "duration_seconds": self.duration_seconds,
            "total_kills": self.total_kills,
            "total_revives": self.total_revives,
            "total_vehicles_destroyed": self.total_vehicles_destroyed,
            "total_flags_captured": self.total_flags_captured,
            "total_teamkills": self.total_teamkills,
            "total_suicides": self.total_suicides,
            "squad_names": self.squad_names,
            "kill_positions": self.kill_positions,
            "movement": self._movement_dict(),
            "spawns": self.spawns,
            "flags": self.flags,
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
                    "kit_kills": ps.kit_kills,
                    "kit_deaths": ps.kit_deaths,
                    "vehicle_kills": ps.vehicle_kills,
                    "vehicles_destroyed": ps.vehicles_destroyed,
                    "vehicles_destroyed_by_type": ps.vehicles_destroyed_by_type,
                    "seat_kills": ps.seat_kills,
                    "squad": ps.squad,
                    "teamkills": ps.teamkills,
                    "suicides": ps.suicides,
                    "best_killstreak": ps.best_killstreak,
                    "first_blood": ps.first_blood,
                    "clutch_kills": ps.clutch_kills,
                    "alive_ticks": ps.alive_ticks,
                    "life_count": ps.life_count,
                    "cohesion_sum": round(ps.cohesion_sum, 1),
                    "cohesion_samples": ps.cohesion_samples,
                    "flags_captured": ps.flags_captured,
                    "kill_weapons": ps.kill_weapons,
                    "death_weapons": ps.death_weapons,
                }
                for pid, ps in self.players.items()
            },
        }

    def _movement_dict(self) -> Dict[str, Any]:
        """Reparte los eventos de movimiento en MOVE_PHASES fases por fracción de ronda
        (frame/duration) → {grid, phases, team1:[[ph,gx,gy,c]], team2:[…]}."""
        dur = max(self.duration_ticks, 1)
        agg = {1: {}, 2: {}}
        for gx, gy, team, frame in self.move_events:
            if team not in (1, 2):
                continue
            ph = min(MOVE_PHASES - 1, frame * MOVE_PHASES // dur)
            key = (ph, gx, gy)
            agg[team][key] = agg[team].get(key, 0) + 1
        return {
            "grid": self.move_grid_size, "phases": MOVE_PHASES,
            "team1": [[ph, gx, gy, c] for (ph, gx, gy), c in agg[1].items()],
            "team2": [[ph, gx, gy, c] for (ph, gx, gy), c in agg[2].items()],
        }


def parse_demo(reader: DemoReader) -> RoundStats:
    """Parse a PRDemo stream and return aggregated round statistics."""
    stats = RoundStats()

    # Track active entities
    player_names: Dict[int, str] = {}  # player_id -> ign
    vehicle_names: Dict[int, str] = {}  # vehicle_id -> name
    player_vehicles: Dict[int, int] = {}  # player_id -> vehicle_id
    player_seats: Dict[int, str] = {}  # player_id -> asiento actual (gunner/driver/pilot…)
    last_kit: Dict[int, str] = {}  # player_id -> último kit conocido (para contar solo cambios)
    last_pos: Dict[int, tuple] = {}  # player_id -> última posición (x,y,z) conocida
    last_squad: Dict[int, int] = {}  # player_id -> escuadra actual (0 = sin escuadra)
    ever_squad: Dict[int, bool] = {}  # pid -> alguna vez estuvo en una escuadra
    killstreak: Dict[int, int] = defaultdict(int)  # pid -> racha actual de kills sin morir
    spawn_tick: Dict[int, int] = {}  # pid -> tick en que revivió/spawneó (para tiempo vivo)
    pending_spawn: set = set()       # pids que acaban de revivir (esperan su 1ra posición)
    move_last: Dict[int, tuple] = {}  # pid -> última celda de movimiento registrada
    flag_owners: Dict[int, int] = {}  # cp_id -> team
    total_ticks = 0       # cantidad de mensajes TICKS (frames de demo)
    first_blood_done = False
    last_cohesion_tick = -1000
    COHESION_EVERY = 33   # muestrear cohesión/movimiento ~cada 33 frames (~10s)
    CLUTCH_TICKETS = 25   # umbral de tickets propios para considerar una baja "clutch"
    MOVE_G = stats.move_grid_size  # grilla de densidad de movimiento
    tickets1_latest = 0
    tickets2_latest = 0

    def grid_cell(x: float, z: float):
        """World (x,z) → celda (gx,gy) en la grilla de movimiento, o None si OOB.
        Misma normalización centrada al mapa que el heatmap de muertes."""
        ms = stats.map_size
        if ms <= 0:
            return None
        # El mapa abarca ±512·MapSize (ref. realitytracker: fullSize = MapSize*1024),
        # no ±500 — usar 512/1024 para alinear con el minimapa.
        full = ms * 1024.0
        nx = (x + ms * 512.0) / full
        nz = (z + ms * 512.0) / full
        if nx < 0 or nx > 1 or nz < 0 or nz > 1:
            return None
        return (min(MOVE_G - 1, int(nx * MOVE_G)), min(MOVE_G - 1, int(nz * MOVE_G)))

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
            stats.demo_time_per_tick = sd.demo_time_per_tick

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
                if pu.squad is not None:
                    last_squad[pu.id] = pu.squad
                    if pu.squad:
                        ever_squad[pu.id] = True
                if pu.position is not None:
                    last_pos[pu.id] = (pu.position.x, pu.position.y, pu.position.z)
                    # Spawn: la 1ra posición tras revivir = punto de aparición.
                    if pu.id in pending_spawn and ps.team in (1, 2):
                        stats.spawns.append([pu.position.x, pu.position.z, ps.team])
                        pending_spawn.discard(pu.id)
                # is_alive solo llega en transiciones (spawn/muerte) → mide tiempo vivo.
                if pu.is_alive is not None:
                    if pu.is_alive:
                        spawn_tick[pu.id] = total_ticks
                        pending_spawn.add(pu.id)  # capturar su próximo punto como spawn
                    else:
                        st_ = spawn_tick.pop(pu.id, None)
                        if st_ is not None:
                            ps.alive_ticks += max(0, total_ticks - st_)
                            ps.life_count += 1
                # vehicle.id >= 0 → subió a un vehículo; id < 0 → se bajó.
                # Antes solo se registraba la subida y nunca la bajada, así que las
                # kills a pie tras desmontar (p.ej. de un camión de logística) se
                # atribuían al vehículo → vehicle_kills inflado con transportes.
                if pu.vehicle is not None:
                    if pu.vehicle.id >= 0:
                        player_vehicles[pu.id] = pu.vehicle.id
                        if pu.vehicle.seat_name:
                            player_seats[pu.id] = pu.vehicle.seat_name
                    else:
                        player_vehicles.pop(pu.id, None)
                        player_seats.pop(pu.id, None)

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
            is_suicide = kill.attacker_id == kill.victim_id
            is_teamkill = (not is_suicide and victim_ps is not None
                           and attacker.team != -1 and attacker.team == victim_ps.team)
            if is_suicide:
                stats.total_suicides += 1
                attacker.suicides += 1
            elif is_teamkill:
                stats.total_teamkills += 1
                attacker.teamkills += 1

            # Desempeño por kit: atribuir la baja al kit que el atacante tenía puesto
            # (solo frags reales, no suicidio ni teamkill). Best-effort: requiere
            # haber visto ya el kit del jugador.
            if not is_suicide and not is_teamkill:
                akit = last_kit.get(kill.attacker_id)
                if akit:
                    attacker.kit_kills[akit] = attacker.kit_kills.get(akit, 0) + 1
                # Kills por asiento del vehículo (artillero/conductor/piloto…).
                aseat = player_seats.get(kill.attacker_id)
                if aseat:
                    attacker.seat_kills[aseat] = attacker.seat_kills.get(aseat, 0) + 1
                # Racha de kills sin morir (mejor de la ronda).
                killstreak[kill.attacker_id] += 1
                if killstreak[kill.attacker_id] > attacker.best_killstreak:
                    attacker.best_killstreak = killstreak[kill.attacker_id]
                # First blood: primera baja real de la ronda.
                if not first_blood_done:
                    attacker.first_blood = 1
                    first_blood_done = True
                # Clutch: baja con el equipo propio sangrando (pocos tickets).
                team_tickets = tickets1_latest if attacker.team == 1 else (
                    tickets2_latest if attacker.team == 2 else None)
                if team_tickets is not None and 0 < team_tickets <= CLUTCH_TICKETS:
                    attacker.clutch_kills += 1

            # Track vehicle kills
            if kill.attacker_id in player_vehicles:
                v_id = player_vehicles[kill.attacker_id]
                v_name = vehicle_names.get(v_id, f"Vehicle_{v_id}")
                attacker.vehicle_kills[v_name] = attacker.vehicle_kills.get(v_name, 0) + 1

            # Posición de la muerte + del atacante + distancia (para heatmap de muertes,
            # francotiradores y líneas de fuego). Solo frags reales.
            if not is_suicide and not is_teamkill:
                vpos = last_pos.get(kill.victim_id)
                if vpos is not None:
                    vteam = stats.players[kill.victim_id].team if kill.victim_id in stats.players else -1
                    apos = last_pos.get(kill.attacker_id)
                    ateam = attacker.team
                    v_ign = stats.players[kill.victim_id].ign if kill.victim_id in stats.players else ""
                    a_ign = attacker.ign
                    if apos is not None:
                        dist = round(((apos[0] - vpos[0]) ** 2 + (apos[2] - vpos[2]) ** 2) ** 0.5, 1)
                        stats.kill_positions.append([vpos[0], vpos[2], vteam, apos[0], apos[2], ateam, dist, kill.weapon, v_ign, a_ign])
                    else:
                        stats.kill_positions.append([vpos[0], vpos[2], vteam, None, None, ateam, -1, kill.weapon, v_ign, a_ign])

            victim = get_player(kill.victim_id)
            victim.death_weapons[kill.weapon] = victim.death_weapons.get(kill.weapon, 0) + 1
            killstreak[kill.victim_id] = 0  # murió → se corta su racha
            # Muerte atribuida al kit que la víctima tenía puesto.
            vkit = last_kit.get(kill.victim_id)
            if vkit:
                victim.kit_deaths[vkit] = victim.kit_deaths.get(vkit, 0) + 1

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
                killer = get_player(vd.killer_id)
                killer.vehicles_destroyed += 1
                # Qué vehículo destruyó (tanque/heli/jeep…), no solo el conteo.
                v_name = vehicle_names.get(vd.id)
                if v_name:
                    killer.vehicles_destroyed_by_type[v_name] = \
                        killer.vehicles_destroyed_by_type.get(v_name, 0) + 1

        # ── Flag List ────────────────────────────────────────────────
        elif raw_msg.msg_type == MessageType.FLAG_LIST:
            stats.flags = [[f.position.x, f.position.z, f.owning_team, f.radius]
                           for f in decoded]

        # ── Squad Name ───────────────────────────────────────────────
        elif raw_msg.msg_type == MessageType.SQUAD_NAME:
            sn: SquadName = decoded
            stats.squad_names[sn.team_squad] = sn.squad_name

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
            total_ticks += 1  # cada mensaje TICKS = un frame de demo
            # Cohesión de escuadra: cada ~COHESION_EVERY frames, agrupar a los
            # jugadores por (equipo, escuadra) y medir la distancia de cada uno al
            # centroide de su escuadra (menor = más juntos).
            if total_ticks - last_cohesion_tick >= COHESION_EVERY:
                last_cohesion_tick = total_ticks
                groups: Dict[tuple, list] = defaultdict(list)
                for pid, pos in last_pos.items():
                    pp = stats.players.get(pid)
                    if pp is None or pp.team not in (1, 2):
                        continue
                    # Movimiento (rutas): registrar solo cuando el jugador entra a una
                    # celda NUEVA → traza recorridos, no campeo ni muertos. Guardamos el
                    # frame para repartir en fases temporales (slider) al cerrar la ronda.
                    cell = grid_cell(pos[0], pos[2])
                    if cell is not None and move_last.get(pid) != cell:
                        stats.move_events.append([cell[0], cell[1], pp.team, total_ticks])
                        move_last[pid] = cell
                    # Cohesión de escuadra (distancia al centroide del squad).
                    sq = last_squad.get(pid, 0)
                    if sq:
                        groups[(pp.team, sq)].append((pid, pos))
                for members in groups.values():
                    if len(members) < 2:
                        continue
                    cx = sum(p[1][0] for p in members) / len(members)
                    cz = sum(p[1][2] for p in members) / len(members)
                    for pid, pos in members:
                        d = ((pos[0] - cx) ** 2 + (pos[2] - cz) ** 2) ** 0.5
                        stats.players[pid].cohesion_sum += d
                        stats.players[pid].cohesion_samples += 1

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
    stats.duration_seconds = round(total_ticks * stats.demo_time_per_tick, 1)

    # Cerrar las vidas que seguían abiertas al final (spawn sin muerte registrada).
    for pid, st_ in spawn_tick.items():
        if pid in stats.players:
            stats.players[pid].alive_ticks += max(0, total_ticks - st_)
            stats.players[pid].life_count += 1

    # Escuadra de cada jugador: la última conocida; si alguna vez estuvo en una
    # pero terminó solo, marcamos 1 para no perder el "jugó en escuadra".
    for pid in set(last_squad) | set(ever_squad):
        if pid in stats.players:
            stats.players[pid].squad = last_squad.get(pid, 0) or (1 if ever_squad.get(pid) else 0)

    # Reportar tipos de mensaje no reconocidos (descubrir contenido nuevo de PR).
    if reader.unknown_types:
        logger.info(
            "Tipos de mensaje PRDemo desconocidos: %s",
            ", ".join(f"0x{t:02X}×{n}" for t, n in reader.unknown_types.most_common()),
        )

    return stats


def parse_demo_file(path: str) -> RoundStats:
    """Parse a .PRdemo file from disk and return round statistics."""
    reader = DemoReader.from_file(path)
    return parse_demo(reader)
