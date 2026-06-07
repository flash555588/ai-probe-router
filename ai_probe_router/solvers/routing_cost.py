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
    if box.contains(x1, y1) or box.contains(x2, y2):
        return True

    corners = [
        (box.min_x, box.min_y),
        (box.max_x, box.min_y),
        (box.max_x, box.max_y),
        (box.min_x, box.max_y),
    ]
    edges = list(zip(corners, corners[1:] + corners[:1]))
    return any(
        _segments_intersect((x1, y1), (x2, y2), start, end)
        for start, end in edges
    )


def _segments_intersect(
    a1: tuple[float, float],
    a2: tuple[float, float],
    b1: tuple[float, float],
    b2: tuple[float, float],
) -> bool:
    def orient(
        p: tuple[float, float],
        q: tuple[float, float],
        r: tuple[float, float],
    ) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def on_segment(
        p: tuple[float, float],
        q: tuple[float, float],
        r: tuple[float, float],
    ) -> bool:
        return (
            min(p[0], r[0]) <= q[0] <= max(p[0], r[0])
            and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])
        )

    o1 = orient(a1, a2, b1)
    o2 = orient(a1, a2, b2)
    o3 = orient(b1, b2, a1)
    o4 = orient(b1, b2, a2)
    eps = 1e-9

    if o1 * o2 < 0 and o3 * o4 < 0:
        return True
    if abs(o1) <= eps and on_segment(a1, b1, a2):
        return True
    if abs(o2) <= eps and on_segment(a1, b2, a2):
        return True
    if abs(o3) <= eps and on_segment(b1, a1, b2):
        return True
    if abs(o4) <= eps and on_segment(b1, a2, b2):
        return True
    return False
