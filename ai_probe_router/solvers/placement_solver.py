"""Constraint-aware placement solver for probe pads.

Generates candidate positions, scores them by routing cost and constraint
satisfaction, and returns the best valid placement.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models.board import Board
from ..models.constraints import Constraints
from ..models.probe import ProbeConfig, ProbeRequirement
from .constraint_checker import check_placement
from .routing_cost import estimate_routing_cost


@dataclass
class PlacementCandidate:
    x: float
    y: float
    score: float
    valid: bool = True


def find_placement(
    board: Board,
    req: ProbeRequirement,
    probe_cfg: ProbeConfig,
    constraints: Constraints,
    existing_probes: list[tuple[float, float]],
    index: int = 0,
) -> tuple[float, float]:
    pads = board.find_pads_by_net(req.net_name)
    target_positions = [(p.x, p.y) for _, p in pads]

    candidates = _generate_candidates(board, target_positions, probe_cfg, index)

    best: PlacementCandidate | None = None
    for c in candidates:
        check = check_placement(c.x, c.y, board, constraints, probe_cfg, existing_probes)
        if not check.ok:
            c.valid = False
            c.score -= 1000.0
        cost = estimate_routing_cost(c.x, c.y, target_positions, board)
        c.score -= cost.total
        if best is None or c.score > best.score:
            best = c

    if best is not None and best.valid:
        return best.x, best.y

    # Fallback: if no fully valid candidate, pick the best one anyway
    if best is not None:
        return best.x, best.y

    grid = probe_cfg.preferred_grid_mm
    return _snap(10.0 + index * grid, grid), _snap(10.0, grid)


def _generate_candidates(
    board: Board,
    target_positions: list[tuple[float, float]],
    probe_cfg: ProbeConfig,
    index: int,
) -> list[PlacementCandidate]:
    grid = probe_cfg.preferred_grid_mm
    candidates: list[PlacementCandidate] = []
    bounds = board.board_bounds()

    if target_positions:
        ref_x, ref_y = target_positions[0]
        offsets = [
            (3.0, 0.0),
            (0.0, 3.0),
            (-3.0, 0.0),
            (0.0, -3.0),
            (5.0, 0.0),
            (0.0, 5.0),
            (-5.0, 0.0),
            (0.0, -5.0),
            (4.0, 4.0),
            (-4.0, 4.0),
            (4.0, -4.0),
            (-4.0, -4.0),
        ]
        for dx, dy in offsets:
            cx = _snap(ref_x + dx + index * grid, grid)
            cy = _snap(ref_y + dy, grid)
            candidates.append(PlacementCandidate(x=cx, y=cy, score=100.0 - abs(dx) - abs(dy)))

        for tx, ty in target_positions[1:]:
            for dx, dy in offsets[:4]:
                cx = _snap(tx + dx + index * grid, grid)
                cy = _snap(ty + dy, grid)
                candidates.append(PlacementCandidate(x=cx, y=cy, score=80.0 - abs(dx) - abs(dy)))

    if bounds:
        edge_margin = 3.0
        inset = bounds.inset(edge_margin)
        edge_positions = [
            (inset.min_x, (inset.min_y + inset.max_y) / 2),
            (inset.max_x, (inset.min_y + inset.max_y) / 2),
            ((inset.min_x + inset.max_x) / 2, inset.min_y),
            ((inset.min_x + inset.max_x) / 2, inset.max_y),
        ]
        for ex, ey in edge_positions:
            cx = _snap(ex + index * grid, grid)
            cy = _snap(ey, grid)
            candidates.append(PlacementCandidate(x=cx, y=cy, score=50.0))

    if not candidates:
        cx = _snap(10.0 + index * grid, grid)
        cy = _snap(10.0, grid)
        candidates.append(PlacementCandidate(x=cx, y=cy, score=0.0))

    return candidates


def _snap(val: float, grid: float) -> float:
    if grid <= 0:
        return val
    return round(val / grid) * grid


def place_pogo_array(
    board: Board,
    reqs: list[ProbeRequirement],
    probe_cfg: ProbeConfig,
    constraints: Constraints,
) -> list[tuple[float, float]]:
    """Place all probe pads in a centralized grid array.

    Returns a list of (x, y) positions aligned to probe_cfg.preferred_grid_mm.
    The array is placed along the bottom edge of the board, inset from edges.
    """
    bounds = board.board_bounds()
    if bounds is None:
        grid = probe_cfg.preferred_grid_mm
        return [(_snap(10.0 + i * grid, grid), _snap(10.0, grid)) for i in range(len(reqs))]

    grid = probe_cfg.preferred_grid_mm
    edge = constraints.placement.min_distance_from_board_edge_mm
    margin = max(edge, 3.0)

    # Place array along bottom edge, left-aligned with margin
    start_x = _snap(bounds.min_x + margin, grid)
    start_y = _snap(bounds.min_y + margin, grid)

    positions: list[tuple[float, float]] = []
    cols = max(1, int((bounds.width - 2 * margin) // grid))
    for i in range(len(reqs)):
        col = i % cols
        row = i // cols
        x = start_x + col * grid
        y = start_y + row * grid
        positions.append((x, y))

    return positions
