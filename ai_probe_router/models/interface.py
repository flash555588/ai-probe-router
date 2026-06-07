from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InterfaceSpec:
    type: str
    pins: list[str] = field(default_factory=list)
    address_configurable: bool = False
    max_bus_speed: str = ""

