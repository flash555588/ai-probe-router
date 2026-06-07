from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BusSpec:
    type: str
    name: str = ""
    signals: list[str] = field(default_factory=list)
    speed: str = ""
    voltage_domain: str = ""

