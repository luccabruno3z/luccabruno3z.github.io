"""Message type constants for the PRDemo binary protocol."""

from enum import IntEnum


class MessageType(IntEnum):
    SERVER_DETAILS = 0x00
    DOD_LIST = 0x01

    PLAYER_UPDATE = 0x10
    PLAYER_ADD = 0x11
    PLAYER_REMOVE = 0x12

    VEHICLE_UPDATE = 0x20
    VEHICLE_ADD = 0x21
    VEHICLE_DESTROYED = 0x22

    FOB_ADD = 0x30
    FOB_REMOVE = 0x31

    FLAG_UPDATE = 0x40
    FLAG_LIST = 0x41

    KILL = 0x50
    CHAT = 0x51

    TICKETS_TEAM1 = 0x52
    TICKETS_TEAM2 = 0x53

    RALLY_ADD = 0x60
    RALLY_REMOVE = 0x61

    CACHE_ADD = 0x70
    CACHE_REMOVE = 0x71
    CACHE_REVEAL = 0x72
    INTEL_CHANGE = 0x73

    MARKER_ADD = 0x80
    MARKER_REMOVE = 0x81

    PROJ_UPDATE = 0x90
    PROJ_ADD = 0x91
    PROJ_REMOVE = 0x92

    REVIVE = 0xA0
    KIT_ALLOCATED = 0xA1
    SQUAD_NAME = 0xA2
    SL_ORDERS = 0xA3

    ROUND_END = 0xF0
    TICKS = 0xF1

    PRIVATE_MESSAGE = 0xFD
    ERROR_MESSAGE = 0xFE


# PlayerUpdate flag bits
class PlayerFlag(IntEnum):
    TEAM = 1
    SQUAD = 2
    VEHICLE = 4
    HEALTH = 8
    SCORE = 16
    TEAMWORK_SCORE = 32
    KILLS = 64
    # 128 is unused
    DEATHS = 256
    PING = 512
    # 1024 is unused
    IS_ALIVE = 2048
    IS_JOINING = 4096
    POSITION = 8192
    ROTATION = 16384
    KIT_NAME = 32768


# VehicleUpdate flag bits
class VehicleFlag(IntEnum):
    TEAM = 1
    POSITION = 2
    ROTATION = 4
    HEALTH = 8
