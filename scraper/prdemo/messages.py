"""Message structs decoded from PRDemo binary protocol.

Each decode_* function takes a BinReader positioned at the payload
(after the message type byte) and returns a dataclass instance.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from .decode import BinReader
from .types import MessageType, PlayerFlag, VehicleFlag


# ── Common types ─────────────────────────────────────────────────────────────

@dataclass
class Position:
    x: int
    y: int
    z: int


@dataclass
class MapInfo:
    name: str
    gamemode: str
    layer: int


# ── Server Details (0x00) ────────────────────────────────────────────────────

@dataclass
class ServerDetails:
    version: int
    demo_time_per_tick: float
    ip_port: str
    server_name: str
    max_players: int
    round_length: int
    briefing_time: int
    map: MapInfo
    blufor_team: str
    opfor_team: str
    start_time: int
    tickets1: int
    tickets2: int
    map_size: float


def decode_server_details(r: BinReader) -> ServerDetails:
    return ServerDetails(
        version=r.read_int32(),
        demo_time_per_tick=r.read_float32(),
        ip_port=r.read_string(),
        server_name=r.read_string(),
        max_players=r.read_uint8(),
        round_length=r.read_uint16(),
        briefing_time=r.read_uint16(),
        map=MapInfo(
            name=r.read_string(),
            gamemode=r.read_string(),
            layer=r.read_uint8(),
        ),
        blufor_team=r.read_string(),
        opfor_team=r.read_string(),
        start_time=r.read_uint32(),
        tickets1=r.read_uint16(),
        tickets2=r.read_uint16(),
        map_size=r.read_float32(),
    )


# ── Player Add (0x11) ───────────────────────────────────────────────────────

@dataclass
class PlayerAdd:
    id: int
    ign: str
    hash: str
    ip: str


def decode_player_add(r: BinReader) -> PlayerAdd:
    return PlayerAdd(
        id=r.read_uint8(),
        ign=r.read_string(),
        hash=r.read_string(),
        ip=r.read_string(),
    )


def decode_players_add(r: BinReader) -> List[PlayerAdd]:
    players = []
    while r.remaining > 0:
        try:
            players.append(decode_player_add(r))
        except EOFError:
            break
    return players


# ── Player Remove (0x12) ─────────────────────────────────────────────────────

@dataclass
class PlayerRemove:
    id: int


def decode_player_remove(r: BinReader) -> PlayerRemove:
    return PlayerRemove(id=r.read_uint8())


# ── Player Update (0x10) ─────────────────────────────────────────────────────

@dataclass
class PlayerVehicle:
    id: int
    seat_name: Optional[str] = None
    seat_number: Optional[int] = None


@dataclass
class PlayerUpdate:
    id: int
    flags: int
    team: Optional[int] = None
    squad: Optional[int] = None
    vehicle: Optional[PlayerVehicle] = None
    health: Optional[int] = None
    score: Optional[int] = None
    teamwork_score: Optional[int] = None
    kills: Optional[int] = None
    deaths: Optional[int] = None
    ping: Optional[int] = None
    is_alive: Optional[bool] = None
    is_joining: Optional[bool] = None
    position: Optional[Position] = None
    rotation: Optional[int] = None
    kit_name: Optional[str] = None


def _decode_player_vehicle(r: BinReader) -> PlayerVehicle:
    vid = r.read_int16()
    if vid >= 0:
        seat_name = r.read_string()
        seat_number = r.read_int8()
        return PlayerVehicle(id=vid, seat_name=seat_name, seat_number=seat_number)
    return PlayerVehicle(id=vid)


def _decode_one_player_update(r: BinReader) -> PlayerUpdate:
    flags = r.read_uint16()
    player_id = r.read_uint8()

    update = PlayerUpdate(id=player_id, flags=flags)

    if flags & PlayerFlag.TEAM:
        update.team = r.read_int8()
    if flags & PlayerFlag.SQUAD:
        update.squad = r.read_uint8()
    if flags & PlayerFlag.VEHICLE:
        update.vehicle = _decode_player_vehicle(r)
    if flags & PlayerFlag.HEALTH:
        update.health = r.read_int8()
    if flags & PlayerFlag.SCORE:
        update.score = r.read_int16()
    if flags & PlayerFlag.TEAMWORK_SCORE:
        update.teamwork_score = r.read_int16()
    if flags & PlayerFlag.KILLS:
        update.kills = r.read_int16()
    if flags & PlayerFlag.DEATHS:
        update.deaths = r.read_int16()
    if flags & PlayerFlag.PING:
        update.ping = r.read_int16()
    if flags & PlayerFlag.IS_ALIVE:
        update.is_alive = r.read_bool()
    if flags & PlayerFlag.IS_JOINING:
        update.is_joining = r.read_bool()
    if flags & PlayerFlag.POSITION:
        update.position = Position(r.read_int16(), r.read_int16(), r.read_int16())
    if flags & PlayerFlag.ROTATION:
        update.rotation = r.read_int16()
    if flags & PlayerFlag.KIT_NAME:
        update.kit_name = r.read_string()

    return update


def decode_players_update(r: BinReader) -> List[PlayerUpdate]:
    updates = []
    while r.remaining > 0:
        try:
            updates.append(_decode_one_player_update(r))
        except EOFError:
            break
    return updates


# ── Kill (0x50) ──────────────────────────────────────────────────────────────

@dataclass
class Kill:
    attacker_id: int
    victim_id: int
    weapon: str


def decode_kill(r: BinReader) -> Kill:
    return Kill(
        attacker_id=r.read_uint8(),
        victim_id=r.read_uint8(),
        weapon=r.read_string(),
    )


# ── Chat (0x51) ──────────────────────────────────────────────────────────────

@dataclass
class Chat:
    channel: int
    player_id: int
    message: str


def decode_chat(r: BinReader) -> Chat:
    return Chat(
        channel=r.read_uint8(),
        player_id=r.read_uint8(),
        message=r.read_string(),
    )


# ── Revive (0xA0) ───────────────────────────────────────────────────────────

@dataclass
class Revive:
    medic_id: int
    revived_id: int


def decode_revive(r: BinReader) -> Revive:
    return Revive(
        medic_id=r.read_uint8(),
        revived_id=r.read_uint8(),
    )


# ── Kit Allocated (0xA1) ─────────────────────────────────────────────────────

@dataclass
class KitAllocated:
    player_id: int
    kit_name: str


def decode_kit_allocated(r: BinReader) -> KitAllocated:
    return KitAllocated(
        player_id=r.read_uint8(),
        kit_name=r.read_string(),
    )


# ── Vehicle Add (0x21) ──────────────────────────────────────────────────────

@dataclass
class VehicleAdd:
    id: int
    name: str
    max_health: int


def decode_vehicle_add(r: BinReader) -> VehicleAdd:
    return VehicleAdd(
        id=r.read_int16(),
        name=r.read_string(),
        max_health=r.read_uint16(),
    )


def decode_vehicles_add(r: BinReader) -> List[VehicleAdd]:
    vehicles = []
    while r.remaining > 0:
        try:
            vehicles.append(decode_vehicle_add(r))
        except EOFError:
            break
    return vehicles


# ── Vehicle Update (0x20) ────────────────────────────────────────────────────

@dataclass
class VehicleUpdate:
    id: int
    flags: int
    team: Optional[int] = None
    position: Optional[Position] = None
    rotation: Optional[int] = None
    health: Optional[int] = None


def _decode_one_vehicle_update(r: BinReader) -> VehicleUpdate:
    flags = r.read_uint8()
    vid = r.read_int16()
    update = VehicleUpdate(id=vid, flags=flags)

    if flags & VehicleFlag.TEAM:
        update.team = r.read_int8()
    if flags & VehicleFlag.POSITION:
        update.position = Position(r.read_int16(), r.read_int16(), r.read_int16())
    if flags & VehicleFlag.ROTATION:
        update.rotation = r.read_int16()
    if flags & VehicleFlag.HEALTH:
        update.health = r.read_int16()

    return update


def decode_vehicles_update(r: BinReader) -> List[VehicleUpdate]:
    updates = []
    while r.remaining > 0:
        try:
            updates.append(_decode_one_vehicle_update(r))
        except EOFError:
            break
    return updates


# ── Vehicle Destroyed (0x22) ─────────────────────────────────────────────────

@dataclass
class VehicleDestroyed:
    id: int
    is_killer_known: bool
    killer_id: int


def decode_vehicle_destroyed(r: BinReader) -> VehicleDestroyed:
    return VehicleDestroyed(
        id=r.read_int16(),
        is_killer_known=r.read_bool(),
        killer_id=r.read_uint8(),
    )


# ── FOB Add (0x30) ──────────────────────────────────────────────────────────

@dataclass
class FobAdd:
    id: int
    team: int
    position: Position


def decode_fob_add(r: BinReader) -> FobAdd:
    return FobAdd(
        id=r.read_int32(),
        team=r.read_uint8(),
        position=Position(r.read_int16(), r.read_int16(), r.read_int16()),
    )


def decode_fobs_add(r: BinReader) -> List[FobAdd]:
    fobs = []
    while r.remaining > 0:
        try:
            fobs.append(decode_fob_add(r))
        except EOFError:
            break
    return fobs


# ── FOB Remove (0x31) ───────────────────────────────────────────────────────

@dataclass
class FobRemove:
    id: int


def decode_fob_remove(r: BinReader) -> FobRemove:
    return FobRemove(id=r.read_int32())


def decode_fobs_remove(r: BinReader) -> List[FobRemove]:
    fobs = []
    while r.remaining > 0:
        try:
            fobs.append(decode_fob_remove(r))
        except EOFError:
            break
    return fobs


# ── Rally Add (0x60) ────────────────────────────────────────────────────────

@dataclass
class RallyAdd:
    team_squad: int
    position: Position


def decode_rally_add(r: BinReader) -> RallyAdd:
    return RallyAdd(
        team_squad=r.read_uint8(),
        position=Position(r.read_int16(), r.read_int16(), r.read_int16()),
    )


# ── Rally Remove (0x61) ─────────────────────────────────────────────────────

@dataclass
class RallyRemove:
    team_squad: int


def decode_rally_remove(r: BinReader) -> RallyRemove:
    return RallyRemove(team_squad=r.read_uint8())


# ── Tickets (0x52, 0x53) ─────────────────────────────────────────────────────

@dataclass
class Tickets:
    tickets: int


def decode_tickets(r: BinReader) -> Tickets:
    return Tickets(tickets=r.read_int16())


# ── Flag Update (0x40) ──────────────────────────────────────────────────────

@dataclass
class FlagUpdate:
    cp_id: int
    owning_team: int


def decode_flag_update(r: BinReader) -> FlagUpdate:
    return FlagUpdate(
        cp_id=r.read_int16(),
        owning_team=r.read_uint8(),
    )


# ── Flag List (0x41) ─────────────────────────────────────────────────────────

@dataclass
class Flag:
    cp_id: int
    owning_team: int
    position: Position
    radius: int


def decode_flags(r: BinReader) -> List[Flag]:
    flags = []
    while r.remaining > 0:
        try:
            flags.append(Flag(
                cp_id=r.read_int16(),
                owning_team=r.read_uint8(),
                position=Position(r.read_int16(), r.read_int16(), r.read_int16()),
                radius=r.read_uint16(),
            ))
        except EOFError:
            break
    return flags


# ── Cache Add (0x70) ─────────────────────────────────────────────────────────

@dataclass
class CacheAdd:
    id: int
    position: Position


def decode_cache_add(r: BinReader) -> CacheAdd:
    return CacheAdd(
        id=r.read_uint8(),
        position=Position(r.read_int16(), r.read_int16(), r.read_int16()),
    )


def decode_caches_add(r: BinReader) -> List[CacheAdd]:
    caches = []
    while r.remaining > 0:
        try:
            caches.append(decode_cache_add(r))
        except EOFError:
            break
    return caches


# ── Cache Remove (0x71) ──────────────────────────────────────────────────────

@dataclass
class CacheRemove:
    id: int


def decode_cache_remove(r: BinReader) -> CacheRemove:
    return CacheRemove(id=r.read_uint8())


# ── Cache Reveal (0x72) ──────────────────────────────────────────────────────

@dataclass
class CacheReveal:
    id: int


def decode_cache_reveal(r: BinReader) -> CacheReveal:
    return CacheReveal(id=r.read_uint8())


def decode_caches_reveal(r: BinReader) -> List[CacheReveal]:
    reveals = []
    while r.remaining > 0:
        try:
            reveals.append(decode_cache_reveal(r))
        except EOFError:
            break
    return reveals


# ── Intel Change (0x73) ──────────────────────────────────────────────────────

@dataclass
class IntelChange:
    intel_count: int


def decode_intel_change(r: BinReader) -> IntelChange:
    return IntelChange(intel_count=r.read_int8())


# ── Squad Name (0xA2) ───────────────────────────────────────────────────────

@dataclass
class SquadName:
    team_squad: int
    squad_name: str


def decode_squad_name(r: BinReader) -> SquadName:
    return SquadName(
        team_squad=r.read_uint8(),
        squad_name=r.read_string(),
    )


# ── Round End (0xF0) ─────────────────────────────────────────────────────────

@dataclass
class RoundEnd:
    winner: int
    tickets1: int
    tickets2: int


def decode_round_end(r: BinReader) -> RoundEnd:
    return RoundEnd(
        winner=r.read_uint8(),
        tickets1=r.read_int16(),
        tickets2=r.read_int16(),
    )


# ── Ticks (0xF1) ─────────────────────────────────────────────────────────────

@dataclass
class Ticks:
    ticks: int


def decode_ticks(r: BinReader) -> Ticks:
    return Ticks(ticks=r.read_uint16())


# ── Projectile Add (0x91) ───────────────────────────────────────────────────

@dataclass
class ProjAdd:
    id: int
    player_id: int
    proj_type: int
    template_name: str
    rotation: int
    position: Position


def decode_proj_add(r: BinReader) -> ProjAdd:
    return ProjAdd(
        id=r.read_uint16(),
        player_id=r.read_uint8(),
        proj_type=r.read_uint8(),
        template_name=r.read_string(),
        rotation=r.read_int16(),
        position=Position(r.read_int16(), r.read_int16(), r.read_int16()),
    )


# ── Projectile Update (0x90) ────────────────────────────────────────────────

@dataclass
class ProjUpdate:
    id: int
    rotation: int
    position: Position


def decode_proj_update(r: BinReader) -> ProjUpdate:
    return ProjUpdate(
        id=r.read_uint16(),
        rotation=r.read_int16(),
        position=Position(r.read_int16(), r.read_int16(), r.read_int16()),
    )


# ── Projectile Remove (0x92) ────────────────────────────────────────────────

@dataclass
class ProjRemove:
    id: int


def decode_proj_remove(r: BinReader) -> ProjRemove:
    return ProjRemove(id=r.read_uint16())


# ── SL Orders (0xA3) ────────────────────────────────────────────────────────

@dataclass
class SLOrder:
    team_squad: int
    order_type: int
    position: Position


def decode_sl_orders(r: BinReader) -> List[SLOrder]:
    orders = []
    while r.remaining > 0:
        try:
            orders.append(SLOrder(
                team_squad=r.read_uint8(),
                order_type=r.read_uint8(),
                position=Position(r.read_int16(), r.read_int16(), r.read_int16()),
            ))
        except EOFError:
            break
    return orders


# ── Dispatch table ──────────────────────────────────────────────────────────

MESSAGE_DECODERS = {
    MessageType.SERVER_DETAILS: decode_server_details,
    MessageType.PLAYER_UPDATE: decode_players_update,
    MessageType.PLAYER_ADD: decode_players_add,
    MessageType.PLAYER_REMOVE: decode_player_remove,
    MessageType.VEHICLE_UPDATE: decode_vehicles_update,
    MessageType.VEHICLE_ADD: decode_vehicles_add,
    MessageType.VEHICLE_DESTROYED: decode_vehicle_destroyed,
    MessageType.FOB_ADD: decode_fobs_add,
    MessageType.FOB_REMOVE: decode_fobs_remove,
    MessageType.RALLY_ADD: decode_rally_add,
    MessageType.RALLY_REMOVE: decode_rally_remove,
    MessageType.FLAG_UPDATE: decode_flag_update,
    MessageType.FLAG_LIST: decode_flags,
    MessageType.KILL: decode_kill,
    MessageType.CHAT: decode_chat,
    MessageType.TICKETS_TEAM1: decode_tickets,
    MessageType.TICKETS_TEAM2: decode_tickets,
    MessageType.CACHE_ADD: decode_caches_add,
    MessageType.CACHE_REMOVE: decode_cache_remove,
    MessageType.CACHE_REVEAL: decode_caches_reveal,
    MessageType.INTEL_CHANGE: decode_intel_change,
    MessageType.REVIVE: decode_revive,
    MessageType.KIT_ALLOCATED: decode_kit_allocated,
    MessageType.SQUAD_NAME: decode_squad_name,
    MessageType.SL_ORDERS: decode_sl_orders,
    MessageType.ROUND_END: decode_round_end,
    MessageType.TICKS: decode_ticks,
    MessageType.PROJ_ADD: decode_proj_add,
    MessageType.PROJ_UPDATE: decode_proj_update,
    MessageType.PROJ_REMOVE: decode_proj_remove,
}
