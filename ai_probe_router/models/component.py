from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Pin:
    number: str
    name: str = ""
    x: float = 0.0
    y: float = 0.0
    electrical_type: str = ""
    net_name: str = ""


@dataclass
class Component:
    ref: str
    value: str
    lib_id: str
    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0
    pins: list[Pin] = field(default_factory=list)
    properties: dict[str, str] = field(default_factory=dict)
    uuid: str = ""
    dnp: bool = False
    is_power_symbol: bool = False
