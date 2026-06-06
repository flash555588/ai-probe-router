from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class ProbeStyle(Enum):
    TEST_PAD = auto()
    POGO_PAD = auto()
    CONNECTOR = auto()


@dataclass
class ProbeRequirement:
    net_name: str
    role: str = "digital"
    required: bool = True
    preferred_devboard_pins: list[str] = field(default_factory=list)
    duplicate_probe_count: int = 1
    current_ma: float = 0.0
    pair_net_name: str = ""


@dataclass
class ProbeConfig:
    style: ProbeStyle = ProbeStyle.TEST_PAD
    side: str = "top"
    pad_diameter_mm: float = 1.5
    min_spacing_mm: float = 2.54
    preferred_grid_mm: float = 2.54
    require_silkscreen_labels: bool = True
    require_fiducials: bool = False
    require_tooling_holes: bool = False
