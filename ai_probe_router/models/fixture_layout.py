"""Multi-board fixture layout configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DutPlacement:
    """Single DUT position on the fixture."""
    index: int
    x_mm: float
    y_mm: float
    rotation_deg: float = 0.0


@dataclass
class FixtureLayout:
    """Configuration for a test fixture that holds multiple DUTs."""
    dut_count: int = 1
    dut_spacing_x_mm: float = 50.0
    dut_spacing_y_mm: float = 50.0
    fixture_width_mm: float = 200.0
    fixture_height_mm: float = 200.0
    backplane_connector: str = ""
    include_led_indicators: bool = True
    include_test_buttons: bool = False
    dut_placements: list[DutPlacement] = field(default_factory=list)
