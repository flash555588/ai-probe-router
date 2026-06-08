"""Fixture design solver: generates multi-DUT test fixture PCB."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from ..models.board import Board
from ..models.fixture_layout import DutPlacement, FixtureLayout


@dataclass
class FixtureDesignResult:
    fixture_layout: FixtureLayout = field(default_factory=FixtureLayout)
    generated_files: list[Path] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def design_fixture(
    source_board: Board,
    layout: FixtureLayout,
    output_dir: Path,
) -> FixtureDesignResult:
    """Generate a multi-DUT test fixture based on a source board layout.

    The solver produces deterministic DUT centers and writes a small CSV placement
    manifest that downstream fixture PCB generation can consume.
    """
    result = FixtureDesignResult(fixture_layout=layout)
    output_dir.mkdir(parents=True, exist_ok=True)

    if layout.dut_count < 1:
        result.errors.append("dut_count must be at least 1")
        return result
    if layout.dut_spacing_x_mm <= 0 or layout.dut_spacing_y_mm <= 0:
        result.errors.append("DUT spacing must be positive")
        return result
    if layout.fixture_width_mm <= 0 or layout.fixture_height_mm <= 0:
        result.errors.append("Fixture dimensions must be positive")
        return result

    board_bounds = source_board.board_bounds()
    dut_width = board_bounds.width if board_bounds is not None else layout.dut_spacing_x_mm / 2
    dut_height = board_bounds.height if board_bounds is not None else layout.dut_spacing_y_mm / 2
    margin_x = max((layout.dut_spacing_x_mm - dut_width) / 2, 0.0)
    margin_y = max((layout.dut_spacing_y_mm - dut_height) / 2, 0.0)

    cols = max(1, int(layout.fixture_width_mm / layout.dut_spacing_x_mm))
    rows = (layout.dut_count + cols - 1) // cols
    required_width = min(layout.dut_count, cols) * layout.dut_spacing_x_mm
    required_height = rows * layout.dut_spacing_y_mm
    if required_width > layout.fixture_width_mm or required_height > layout.fixture_height_mm:
        result.warnings.append(
            "DUT grid exceeds fixture bounds; reduce DUT count or spacing"
        )

    placements: list[DutPlacement] = []
    for i in range(layout.dut_count):
        col = i % cols
        row = i // cols
        x = col * layout.dut_spacing_x_mm + layout.dut_spacing_x_mm / 2
        y = row * layout.dut_spacing_y_mm + layout.dut_spacing_y_mm / 2
        placements.append(DutPlacement(index=i, x_mm=x, y_mm=y))

    result.fixture_layout.dut_placements = placements
    placement_file = output_dir / "fixture_layout.csv"
    _write_fixture_layout_csv(placement_file, layout)
    result.generated_files.append(placement_file)
    result.notes.append(f"Placed {layout.dut_count} DUTs in {cols}-column grid")
    result.notes.append(f"Required grid: {required_width:.1f}x{required_height:.1f} mm")
    result.notes.append(f"DUT envelope: {dut_width:.1f}x{dut_height:.1f} mm")
    if margin_x <= 0 or margin_y <= 0:
        result.warnings.append(
            "DUT spacing leaves no clearance margin around source board envelope"
        )
    result.notes.append(f"Fixture size: {layout.fixture_width_mm}x{layout.fixture_height_mm} mm")
    return result


def _write_fixture_layout_csv(path: Path, layout: FixtureLayout) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "dut_index",
            "x_mm",
            "y_mm",
            "rotation_deg",
            "backplane_connector",
            "include_led_indicators",
            "include_test_buttons",
        ])
        for placement in layout.dut_placements:
            writer.writerow([
                placement.index,
                f"{placement.x_mm:.3f}",
                f"{placement.y_mm:.3f}",
                f"{placement.rotation_deg:.1f}",
                layout.backplane_connector,
                layout.include_led_indicators,
                layout.include_test_buttons,
            ])
