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


class NetSubRole(Enum):
    STRAPPING_PIN = auto()
    ADC_INPUT = auto()
    I2S_DATA = auto()
    I2S_CLOCK = auto()
    SD_DATA = auto()
    SD_CLK = auto()
    BATTERY = auto()
    AUDIO_ANALOG = auto()
    USB_DATA = auto()
    ANALOG_GROUND = auto()


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
    sub_roles: set[NetSubRole] = field(default_factory=set)
    has_testpoint: bool = False
