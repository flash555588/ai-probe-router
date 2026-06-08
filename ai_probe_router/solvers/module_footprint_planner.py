"""Deterministic module footprint preview planner.

Creates candidate footprint placements inside module placement regions
without modifying the source PCB.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..models.board import Board
from ..models.footprint_preview import (
    FootprintPreviewIssue,
    FootprintPreviewResult,
    FootprintPreviewSeverity,
    PlannedFootprint,
)
from .footprint_collision import (
    check_board_bounds,
    check_footprint_collisions,
    check_keepout_violations,
)

if TYPE_CHECKING:
    from ..config import ModuleFootprintPreviewConfig
    from ..models.module import SelectedModule


def plan_module_footprints(
    modules: list[SelectedModule],
    board: Board | None,
    cfg: ModuleFootprintPreviewConfig,
) -> FootprintPreviewResult:
    """Generate planned footprint placements for selected modules.

    * mode='preview' → report only
    * mode='emit_candidate' → may write candidate PCB later
    """
    if not cfg.enable:
        return FootprintPreviewResult()

    result = FootprintPreviewResult()
    existing_refs = _existing_refs(board)
    ref_counter: dict[str, int] = {}

    for sel in modules:
        mod = sel.module
        impl = sel.implementation
        if not impl or not impl.components:
            continue

        # Place components in a simple grid within module region
        region = _module_region(mod, board)
        for comp in impl.components:
            for i in range(comp.count):
                ref = _next_ref(comp.type, ref_counter)
                footprint = _footprint_for(comp)
                if not footprint:
                    if cfg.block_on_missing_footprint:
                        sev = FootprintPreviewSeverity.ERROR
                    else:
                        sev = FootprintPreviewSeverity.WARNING
                    result.issues.append(
                        FootprintPreviewIssue(
                            severity=sev,
                            code="FOOTPRINT_PREVIEW_MISSING_REQUIRED_FOOTPRINT",
                            message=(
                                f"No footprint for {comp.type} in module {mod.name}"
                            ),
                            module_name=mod.name,
                            reference=ref,
                        )
                    )
                    continue

                x, y = _grid_position(i, comp.count, region)
                planned = PlannedFootprint(
                    module_name=mod.name,
                    reference=ref,
                    footprint=footprint,
                    x_mm=x,
                    y_mm=y,
                    rotation_deg=0.0,
                    side="top",
                    role=comp.type,
                )
                result.planned_footprints.append(planned)

    # Run collision and bounds checks
    result.issues.extend(check_footprint_collisions(result.planned_footprints, existing_refs))
    if board is not None:
        result.issues.extend(check_board_bounds(result.planned_footprints, board))
        result.issues.extend(check_keepout_violations(result.planned_footprints, board))

    # Dense-region warning
    if len(result.planned_footprints) >= 10:
        result.issues.append(
            FootprintPreviewIssue(
                severity=FootprintPreviewSeverity.WARNING,
                code="FOOTPRINT_PREVIEW_DENSE_REGION",
                message=f"{len(result.planned_footprints)} planned footprints in region",
            )
        )

    # Candidate-only warning when not writing
    if cfg.mode == "preview":
        result.issues.append(
            FootprintPreviewIssue(
                severity=FootprintPreviewSeverity.INFO,
                code="FOOTPRINT_PREVIEW_CANDIDATE_ONLY",
                message="Preview mode: no PCB modifications made",
            )
        )

    return result


def _existing_refs(board: Board | None) -> set[str]:
    if board is None or not board.footprints:
        return set()
    return {fp.reference for fp in board.footprints}


def _module_region(mod, board: Board | None) -> tuple[float, float, float, float]:
    """Return (x_min, y_min, x_max, y_max) for module placement region."""
    # Use board bounds or a default region
    if board is not None and board.edges:
        xs = [p[0] for edge in board.edges for p in edge]
        ys = [p[1] for edge in board.edges for p in edge]
        if xs and ys:
            return (min(xs), min(ys), max(xs), max(ys))
    return (0.0, 0.0, 100.0, 100.0)


def _next_ref(comp_type: str, counter: dict[str, int]) -> str:
    counter[comp_type] = counter.get(comp_type, 0) + 1
    return f"{comp_type.upper()[:3]}{counter[comp_type]}"


def _footprint_for(comp) -> str:
    """Return footprint name for a component spec."""
    # Use explicit footprint if available
    fp = getattr(comp, "footprint", "")
    if fp:
        return str(fp)
    # Fallback: map common types to standard footprints
    type_map = {
        "mcu": "Package_QFP:LQFP-48_7x7mm_P0.5mm",
        "wifi_mcu": "Package_QFP:LQFP-48_7x7mm_P0.5mm",
        "motor_driver": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
        "power_reg": "Package_TO_SOT_SMD:SOT-23-5",
        "led": "LED_SMD:LED_0603_1608Metric",
        "esd_array": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
        "crystal": "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
        "eeprom": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
        "i2c_eeprom": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
        "matching_network": "Resistor_SMD:R_0402_1005Metric",
        "testpad": "TestPoint:TestPoint_Pad_D1.0mm",
    }
    return type_map.get(comp.type.lower(), "")


def _grid_position(
    index: int,
    count: int,
    region: tuple[float, float, float, float],
) -> tuple[float, float]:
    """Place components in a simple grid inside the region."""
    x_min, y_min, x_max, y_max = region
    margin = 5.0
    width = x_max - x_min - 2 * margin
    height = y_max - y_min - 2 * margin
    cols = max(1, int((count ** 0.5) + 0.5))
    spacing_x = width / (cols + 1)
    spacing_y = height / (cols + 1)
    col = index % cols
    row = index // cols
    x = x_min + margin + spacing_x * (col + 1)
    y = y_min + margin + spacing_y * (row + 1)
    return (x, y)
