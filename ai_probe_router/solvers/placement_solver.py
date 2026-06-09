"""Constraint-aware placement solver for probe pads.

Generates candidate positions, scores them by routing cost and constraint
satisfaction, and returns the best valid placement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..models.board import Board
from ..models.constraints import Constraints
from ..models.net import NetRole, NetSubRole
from ..models.probe import ProbeConfig, ProbeRequirement
from .constraint_checker import Violation, check_placement, placement_clearance_margin
from .routing_cost import estimate_routing_cost
from .signal_aware_scoring import signal_score


@dataclass
class PlacementCandidate:
    x: float
    y: float
    score: float
    valid: bool = True
    clearance_margin: float = 0.0
    warnings: list[str] = field(default_factory=list)


def find_placement(
    board: Board,
    req: ProbeRequirement,
    probe_cfg: ProbeConfig,
    constraints: Constraints,
    existing_probes: list[tuple[float, float]],
    index: int = 0,
    min_target_distance_mm: float = 0.0,
    role: NetRole = NetRole.UNKNOWN,
    sub_roles: set[NetSubRole] | None = None,
    existing_probe_nets: dict[str, tuple[float, float]] | None = None,
) -> tuple[float, float] | None:
    pads = board.find_pads_by_net(req.net_name)
    target_positions = [(p.x, p.y) for _, p in pads]
    if not target_positions:
        return None

    pair_mate_position = (
        existing_probe_nets.get(req.pair_net_name)
        if req.pair_net_name and existing_probe_nets else None
    )
    candidates = _generate_candidates(
        board, target_positions, probe_cfg, index, pair_mate_position,
    )

    best: PlacementCandidate | None = None
    subs = sub_roles or set()
    for c in candidates:
        check = check_placement(
            c.x, c.y, board, constraints, probe_cfg, existing_probes,
            net_name=req.net_name,
        )
        if min_target_distance_mm > 0:
            target_dist = min(
                math.hypot(c.x - tx, c.y - ty)
                for tx, ty in target_positions
            )
            if target_dist < min_target_distance_mm:
                check.add(Violation(
                    rule="target_clearance",
                    message=(
                        f"Probe at ({c.x:.2f}, {c.y:.2f}) is {target_dist:.2f}mm "
                        f"from source pad (min {min_target_distance_mm:.2f}mm)"
                    ),
                    x=c.x,
                    y=c.y,
                ))
        if not check.ok:
            c.valid = False
            c.score -= 1000.0
        else:
            c.clearance_margin = placement_clearance_margin(
                c.x, c.y, board, constraints, probe_cfg, existing_probes,
                net_name=req.net_name,
            )
            if math.isfinite(c.clearance_margin):
                c.score += min(max(c.clearance_margin, 0.0), 5.0) * 8.0
        cost = estimate_routing_cost(c.x, c.y, target_positions, board)
        c.score -= cost.total

        sig_adj, sig_warns = signal_score(c.x, c.y, role, subs, board)
        c.score += sig_adj
        c.warnings.extend(sig_warns)
        c.score += _paired_probe_score(c.x, c.y, req, existing_probe_nets)

        if best is None or c.score > best.score:
            best = c

    if best is not None and best.valid:
        return best.x, best.y

    # No valid candidate found; caller decides fallback behavior
    return None


def _paired_probe_score(
    x: float,
    y: float,
    req: ProbeRequirement,
    existing_probe_nets: dict[str, tuple[float, float]] | None,
) -> float:
    if not req.pair_net_name or not existing_probe_nets:
        return 0.0
    mate = existing_probe_nets.get(req.pair_net_name)
    if mate is None:
        return 0.0

    dist = math.hypot(x - mate[0], y - mate[1])
    if dist < 1.0:
        return -25.0
    if dist <= 5.0:
        return 18.0 - dist
    if dist <= 15.0:
        return max(0.0, 12.0 - (dist - 5.0))
    return -min((dist - 15.0) * 0.5, 20.0)


def _generate_candidates(
    board: Board,
    target_positions: list[tuple[float, float]],
    probe_cfg: ProbeConfig,
    index: int,
    paired_mate_position: tuple[float, float] | None = None,
) -> list[PlacementCandidate]:
    grid = probe_cfg.preferred_grid_mm
    candidates: list[PlacementCandidate] = []
    seen: set[tuple[float, float]] = set()
    bounds = board.board_bounds()

    step = grid if grid > 0 else 2.54
    radii = [step, step * 1.5, step * 2, step * 3, step * 5]
    angle_count = 16
    angle_offset = (index % angle_count) * (math.tau / angle_count / 2)

    if paired_mate_position is not None:
        mx, my = paired_mate_position
        pair_radii = [step, step * 1.5, step * 2, step * 3]
        for radius in pair_radii:
            for angle_i in range(angle_count):
                angle = math.tau * angle_i / angle_count + angle_offset
                cx = _snap(mx + math.cos(angle) * radius, grid)
                cy = _snap(my + math.sin(angle) * radius, grid)
                score = 150.0 - radius * 2.0
                _add_candidate(candidates, seen, board, cx, cy, score)

    for target_i, (tx, ty) in enumerate(target_positions):
        for radius in radii:
            for angle_i in range(angle_count):
                angle = math.tau * angle_i / angle_count + angle_offset
                cx = _snap(tx + math.cos(angle) * radius, grid)
                cy = _snap(ty + math.sin(angle) * radius, grid)
                score = 120.0 - target_i * 8.0 - radius * 2.0
                _add_candidate(candidates, seen, board, cx, cy, score)

    if bounds:
        edge_margin = max(3.0, step)
        inset = bounds.inset(edge_margin)
        edge_positions = [
            (inset.min_x, (inset.min_y + inset.max_y) / 2),
            (inset.max_x, (inset.min_y + inset.max_y) / 2),
            ((inset.min_x + inset.max_x) / 2, inset.min_y),
            ((inset.min_x + inset.max_x) / 2, inset.max_y),
        ]
        for ex, ey in edge_positions:
            cx = _snap(ex, grid)
            cy = _snap(ey, grid)
            _add_candidate(candidates, seen, board, cx, cy, 50.0)

        added = 0
        x = _ceil_to_grid(bounds.min_x + edge_margin, step)
        while x <= bounds.max_x - edge_margin + 1e-9 and added < 5000:
            y = _ceil_to_grid(bounds.min_y + edge_margin, step)
            while y <= bounds.max_y - edge_margin + 1e-9 and added < 5000:
                if board.contains_point(x, y):
                    _add_candidate(candidates, seen, board, x, y, 20.0)
                    added += 1
                y += step
            x += step

    if not candidates:
        cx, cy = target_positions[0]
        _add_candidate(candidates, seen, board, _snap(cx, grid), _snap(cy, grid), 0.0)

    return candidates


def _snap(val: float, grid: float) -> float:
    if grid <= 0:
        return val
    return round(round(val / grid) * grid, 6)


def _ceil_to_grid(val: float, grid: float) -> float:
    if grid <= 0:
        return val
    return round(math.ceil(val / grid) * grid, 6)


def _add_candidate(
    candidates: list[PlacementCandidate],
    seen: set[tuple[float, float]],
    board: Board,
    x: float,
    y: float,
    score: float,
) -> None:
    if board.edges and not board.contains_point(x, y):
        return
    key = (round(x, 4), round(y, 4))
    if key in seen:
        return
    seen.add(key)
    candidates.append(PlacementCandidate(x=x, y=y, score=score))


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

    positions: list[tuple[float, float]] = []
    step = grid if grid > 0 else 2.54
    x = _ceil_to_grid(bounds.min_x + margin, step)
    candidates: list[tuple[float, float]] = []
    while x <= bounds.max_x - margin + 1e-9:
        y = _ceil_to_grid(bounds.min_y + margin, step)
        while y <= bounds.max_y - margin + 1e-9:
            if board.contains_point(x, y):
                candidates.append((x, y))
            y += step
        x += step

    candidates.sort(key=lambda p: (p[1], p[0]))
    for x, y in candidates:
        if len(positions) >= len(reqs):
            break
        req = reqs[len(positions)]
        check = check_placement(
            x, y, board, constraints, probe_cfg, positions,
            net_name=req.net_name,
        )
        if check.ok:
            positions.append((x, y))

    return positions
