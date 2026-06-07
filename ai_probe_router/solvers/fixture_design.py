"""Fixture design solver: generates multi-DUT test fixture PCB."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..models.board import Board
from ..models.fixture_layout import DutPlacement, FixtureLayout


@dataclass
class FixtureDesignResult:
    fixture_layout: FixtureLayout = field(default_factory=FixtureLayout)
    generated_files: list[Path] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def design_fixture(
    source_board: Board,
    layout: FixtureLayout,
    output_dir: Path,
) -> FixtureDesignResult:
    """Generate a multi-DUT test fixture based on a source board layout.

    Currently a placeholder that computes DUT positions in a grid.
    """
    result = FixtureDesignResult(fixture_layout=layout)
    cols = max(1, int(layout.fixture_width_mm / layout.dut_spacing_x_mm))

    placements: list[DutPlacement] = []
    for i in range(layout.dut_count):
        col = i % cols
        row = i // cols
        x = col * layout.dut_spacing_x_mm + layout.dut_spacing_x_mm / 2
        y = row * layout.dut_spacing_y_mm + layout.dut_spacing_y_mm / 2
        placements.append(DutPlacement(index=i, x_mm=x, y_mm=y))

    result.fixture_layout.dut_placements = placements
    result.notes.append(f"Placed {layout.dut_count} DUTs in {cols}-column grid")
    result.notes.append(f"Fixture size: {layout.fixture_width_mm}x{layout.fixture_height_mm} mm")
    return result
