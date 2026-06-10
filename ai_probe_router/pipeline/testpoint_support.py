"""Shared placement and routing helpers for the testpoint phase."""

from __future__ import annotations

import math

from ..config import ProjectConfig
from ..eda_adapters.kicad.pcb_writer import add_track_segment
from ..models.board import Board, BoundingBox, _pad_bounds
from ..models.net import NetRole
from ..models.protection import ProtectionComponent
from ..solvers.grid_router import RouteResult, route_grid


def net_class_for_role(role: NetRole, current_ma: float) -> tuple[float, float]:
    if role == NetRole.POWER:
        if current_ma > 500:
            return 0.5, 0.2
        return 0.3, 0.15
    if role == NetRole.GROUND:
        return 0.3, 0.15
    if role == NetRole.HIGH_SPEED:
        return 0.15, 0.2
    if role == NetRole.ANALOG:
        return 0.2, 0.25
    if role == NetRole.CLOCK:
        return 0.15, 0.2
    return 0.15, 0.15


def protected_probe_distance_mm(protection: ProtectionComponent) -> float:
    package_room = {
        "0402": 4.0,
        "0603": 4.5,
        "0805": 5.0,
    }
    return package_room.get(protection.package, 4.0)


def effective_trace_width(width: float, cfg: ProjectConfig) -> float:
    return max(width, cfg.constraints.manufacturing.min_trace_width_mm, 0.20)


def effective_clearance(clearance: float, cfg: ProjectConfig) -> float:
    return max(
        clearance,
        cfg.constraints.manufacturing.min_clearance_mm,
        cfg.constraints.routing.min_clearance_mm,
        0.20,
    )


def trace_length(points: list[tuple[float, float]]) -> float:
    """Compute total Euclidean length of a polyline."""
    if len(points) < 2:
        return 0.0
    return sum(
        math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1])
        for i in range(1, len(points))
    )


def find_protection_placement(
    board: Board,
    net_name: str,
    probe_x: float,
    probe_y: float,
    protection: ProtectionComponent,
) -> tuple[float, float, float]:
    target = nearest_pad_position(board, net_name, probe_x, probe_y)
    if target is None:
        return probe_x - 2.0, probe_y, 0.0

    tx, ty = target
    dx = probe_x - tx
    dy = probe_y - ty
    dist = math.hypot(dx, dy)
    if dist < 1e-9:
        return probe_x - 2.0, probe_y, 0.0

    # Candidate at midpoint
    cx = (tx + probe_x) / 2
    cy = (ty + probe_y) / 2
    rot = math.degrees(math.atan2(dy, dx))

    # Build occupied zones from all existing pads except current net source
    occupied: list[BoundingBox] = []
    for fp in board.footprints:
        for pad in fp.pads:
            if pad.net_name == net_name:
                continue
            bb = _pad_bounds(pad)
            occupied.append(bb)

    fp_half = {
        "0402": 0.7,
        "0603": 1.0,
        "0805": 1.3,
        "SOT-23-6": 1.8,
    }.get(protection.package, 1.0)
    margin = 2.0

    for frac in [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95]:
        cx = tx + dx * frac
        cy = ty + dy * frac
        # Footprint bbox at this candidate
        f_min_x = cx - fp_half
        f_max_x = cx + fp_half
        f_min_y = cy - fp_half
        f_max_y = cy + fp_half
        clear = True
        for bb in occupied:
            overlaps_x = (
                f_min_x - margin <= bb.max_x
                and f_max_x + margin >= bb.min_x
            )
            overlaps_y = (
                f_min_y - margin <= bb.max_y
                and f_max_y + margin >= bb.min_y
            )
            if overlaps_x and overlaps_y:
                clear = False
                break
        if clear:
            return cx, cy, rot

    # Fallback
    return tx + dx * 0.95, ty + dy * 0.95, rot


def nearest_pad_position(
    board: Board,
    net_name: str,
    x: float,
    y: float,
) -> tuple[float, float] | None:
    pads = board.find_pads_by_net(net_name)
    if not pads:
        return None
    _fp, pad = min(
        pads,
        key=lambda item: math.hypot(x - item[1].x, y - item[1].y),
    )
    return pad.x, pad.y


def add_route_if_clear(
    board: Board,
    net_name: str,
    start: tuple[float, float],
    end: tuple[float, float],
    width: float,
    clearance: float,
    side: str,
) -> RouteResult:
    if start == end:
        return RouteResult(True, [start, end])
    result = route_grid(
        board, net_name, start, end,
        width=width, clearance=clearance, side=side,
    )
    if not result.ok:
        return result
    for a, b in zip(result.points, result.points[1:]):
        add_track_segment(
            board, net_name,
            a[0], a[1], b[0], b[1],
            width=width,
            side=side,
        )
    return result
