from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class NetRole(Enum):
    UNKNOWN = auto()
    POWER = auto()
    GROUND = auto()
    DEBUG = auto()
    COMMUNICATION = auto()
    ANALOG = auto()
    HIGH_SPEED = auto()
    CLOCK = auto()
    RESET = auto()
    GPIO = auto()


@dataclass
class NetNode:
    ref: str
    pin: str


@dataclass
class Net:
    name: str
    net_id: int = 0
    nodes: list[NetNode] = field(default_factory=list)
    net_class: str = "Default"
    role: NetRole = NetRole.UNKNOWN
    has_testpoint: bool = False
