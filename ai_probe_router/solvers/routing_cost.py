"""Estimates routing cost for placement scoring."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..models.board import Board, BoundingBox


@dataclass
class RoutingCost:
    distance: float = 0.0
    via_penalty: float = 0.0
    congestion_penalty: float = 0.0
    total: float = 0.0


def estimate_routing_cost(
    probe_x: float,
    probe_y: float,
    target_pads: list[tuple[float, float]],
    board: Board,
    *,
    via_cost: float = 2.0,
    congestion_radius: float = 5.0,
) -> RoutingCost:
    if not target_pads:
        return RoutingCost(total=float("inf"))

    min_dist = min(math.hypot(probe_x - px, probe_y - py) for px, py in target_pads)

    all_pads = board.all_pad_positions()
    nearby = sum(
        1 for px, py, _ in all_pads
        if math.hypot(probe_x - px, probe_y - py) < congestion_radius
    )
    congestion = nearby * 0.5

    needs_via = _likely_needs_via(probe_x, probe_y, target_pads, board)
    via_pen = via_cost if needs_via else 0.0

    total = min_dist + via_pen + congestion
    return RoutingCost(
        distance=min_dist,
        via_penalty=via_pen,
        congestion_penalty=congestion,
        total=total,
    )


def _likely_needs_via(
    probe_x: float, probe_y: float,
    target_pads: list[tuple[float, float]],
    board: Board,
) -> bool:
    if not target_pads:
        return False
    nearest_x, nearest_y = min(
        target_pads, key=lambda p: math.hypot(probe_x - p[0], probe_y - p[1])
    )
    for fp in board.footprints:
        if fp.ref.startswith("TP"):
            continue
        fb = board.footprint_bounds(fp)
        if _segment_intersects_box(probe_x, probe_y, nearest_x, nearest_y, fb):
            return True
    return False


def _segment_intersects_box(
    x1: float, y1: float, x2: float, y2: float,
    box: "BoundingBox",
) -> bool:
    mid_x = (x1 + x2) / 2
    mid_y = (y1 + y2) / 2
    if box.contains(mid_x, mid_y):
        return True
    quarter_pts = [
        (x1 + (x2 - x1) * 0.25, y1 + (y2 - y1) * 0.25),
        (x1 + (x2 - x1) * 0.75, y1 + (y2 - y1) * 0.75),
    ]
    return any(box.contains(px, py) for px, py in quarter_pts)
