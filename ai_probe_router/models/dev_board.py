from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DevBoardPin:
    name: str
    capabilities: list[str] = field(default_factory=list)
    alternate_functions: list[str] = field(default_factory=list)
    current_rating_ma: float = 25.0
    is_power: bool = False
    is_ground: bool = False
    fixed: bool = False


@dataclass
class DevelopmentBoard:
    name: str
    connector_type: str = "dual_row_header"
    pitch_mm: float = 2.54
    pins_per_row: int = 20
    pins: list[DevBoardPin] = field(default_factory=list)
