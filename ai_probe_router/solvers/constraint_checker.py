"""Validates probe placement against electrical, mechanical, and manufacturing constraints."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..models.board import Board, BoundingBox
from ..models.constraints import Constraints
from ..models.probe import ProbeConfig


@dataclass
class Violation:
    rule: str
    message: str
    x: float = 0.0
    y: float = 0.0
    severity: str = "error"


@dataclass
class CheckResult:
    ok: bool = True
    violations: list[Violation] = field(default_factory=list)

    def add(self, v: Violation) -> None:
        self.violations.append(v)
        if v.severity == "error":
            self.ok = False


def check_placement(
    x: float,
    y: float,
    board: Board,
    constraints: Constraints,
    probe: ProbeConfig,
    existing_probes: list[tuple[float, float]] | None = None,
) -> CheckResult:
    result = CheckResult()
    bounds = board.board_bounds()
    if bounds is None:
        result.add(Violation(
            rule="board_outline", message="No board outline found", severity="warning",
        ))
        return result

    _check_board_edge(x, y, bounds, constraints.placement.min_distance_from_board_edge_mm, result)
    _check_inside_board(x, y, bounds, result)
    _check_component_collision(x, y, probe.pad_diameter_mm, board, result)
    if existing_probes:
        _check_probe_spacing(x, y, existing_probes, probe.min_spacing_mm, result)
    _check_pad_size(probe.pad_diameter_mm, constraints.manufacturing, result)

    return result


def validate_all_probes(
    probes: list[tuple[float, float, str]],
    board: Board,
    constraints: Constraints,
    probe_cfg: ProbeConfig,
) -> CheckResult:
    result = CheckResult()
    placed: list[tuple[float, float]] = []
    for x, y, net_name in probes:
        single = check_placement(x, y, board, constraints, probe_cfg, placed)
        for v in single.violations:
            v.message = f"[{net_name}] {v.message}"
            result.add(v)
        placed.append((x, y))
    return result


def _check_board_edge(
    x: float, y: float, bounds: BoundingBox, min_dist: float, result: CheckResult,
) -> None:
    dist = bounds.distance_to_edge(x, y)
    if bounds.contains(x, y) and dist < min_dist:
        result.add(Violation(
            rule="board_edge_clearance",
            message=f"Probe at ({x:.2f}, {y:.2f}) is {dist:.2f}mm from board edge "
                    f"(min {min_dist:.2f}mm)",
            x=x, y=y,
        ))


def _check_inside_board(x: float, y: float, bounds: BoundingBox, result: CheckResult) -> None:
    if not bounds.contains(x, y):
        result.add(Violation(
            rule="outside_board",
            message=f"Probe at ({x:.2f}, {y:.2f}) is outside the board outline",
            x=x, y=y,
        ))


def _check_component_collision(
    x: float, y: float, pad_diameter: float, board: Board, result: CheckResult,
) -> None:
    pad_radius = pad_diameter / 2
    for fp in board.footprints:
        if fp.ref.startswith("TP"):
            continue
        fp_bounds = board.footprint_bounds(fp)
        expanded = BoundingBox(
            fp_bounds.min_x - pad_radius,
            fp_bounds.min_y - pad_radius,
            fp_bounds.max_x + pad_radius,
            fp_bounds.max_y + pad_radius,
        )
        if expanded.contains(x, y):
            result.add(Violation(
                rule="component_collision",
                message=f"Probe at ({x:.2f}, {y:.2f}) overlaps with {fp.ref} ({fp.value})",
                x=x, y=y,
            ))
            break


def _check_probe_spacing(
    x: float, y: float, existing: list[tuple[float, float]], min_spacing: float,
    result: CheckResult,
) -> None:
    for ex, ey in existing:
        dist = math.hypot(x - ex, y - ey)
        if dist < min_spacing:
            result.add(Violation(
                rule="probe_spacing",
                message=f"Probe at ({x:.2f}, {y:.2f}) is {dist:.2f}mm from another probe "
                        f"(min {min_spacing:.2f}mm)",
                x=x, y=y,
            ))
            return


def _check_pad_size(pad_diameter: float, mfg, result: CheckResult) -> None:
    min_annular = mfg.min_clearance_mm * 2
    if pad_diameter < min_annular:
        result.add(Violation(
            rule="pad_size",
            message=f"Pad diameter {pad_diameter:.2f}mm is too small for manufacturing "
                    f"(min {min_annular:.2f}mm)",
            severity="warning",
        ))
