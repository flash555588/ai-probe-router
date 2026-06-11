"""Validates probe placement against electrical, mechanical, and manufacturing constraints."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..models.board import Board, BoundingBox, Pad
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
    net_name: str = "",
) -> CheckResult:
    result = CheckResult()
    bounds = board.board_bounds()
    if bounds is None:
        result.add(Violation(
            rule="board_outline", message="No board outline found", severity="warning",
        ))
        return result

    _check_board_edge(x, y, board, constraints.placement.min_distance_from_board_edge_mm, result)
    _check_inside_board(x, y, board, result)
    _check_component_collision(
        x, y, probe.pad_diameter_mm, _effective_min_clearance(constraints),
        board, result,
    )
    _check_track_collision(
        x, y, probe.pad_diameter_mm, _effective_min_clearance(constraints),
        board, probe.side, net_name, result,
    )
    if existing_probes:
        _check_probe_spacing(x, y, existing_probes, probe.min_spacing_mm, result)
    _check_pad_size(probe.pad_diameter_mm, constraints.manufacturing, result)

    return result


def placement_clearance_margin(
    x: float,
    y: float,
    board: Board,
    constraints: Constraints,
    probe: ProbeConfig,
    existing_probes: list[tuple[float, float]] | None = None,
    net_name: str = "",
) -> float:
    """Return the nearest remaining clearance margin in millimeters."""
    if not board.contains_point(x, y):
        return -board.distance_to_outline(x, y)

    margin = board.distance_to_outline(x, y)
    margin -= constraints.placement.min_distance_from_board_edge_mm

    min_clearance = _effective_min_clearance(constraints)
    probe_radius = probe.pad_diameter_mm / 2
    score_horizon = 5.0
    for fp in board.footprints:
        if fp.ref.startswith("TP"):
            continue
        fp_bounds = board.footprint_bounds(fp)
        search_radius = probe_radius + min_clearance + score_horizon
        expanded = BoundingBox(
            fp_bounds.min_x - search_radius,
            fp_bounds.min_y - search_radius,
            fp_bounds.max_x + search_radius,
            fp_bounds.max_y + search_radius,
        )
        if not expanded.contains(x, y):
            continue
        for pad in fp.pads:
            pad_margin = _probe_pad_clearance(x, y, probe_radius, pad) - min_clearance
            margin = min(margin, pad_margin)

    if existing_probes:
        for ex, ey in existing_probes:
            spacing_margin = math.hypot(x - ex, y - ey) - probe.min_spacing_mm
            margin = min(margin, spacing_margin)

    route_layer = "F.Cu" if probe.side == "top" else "B.Cu"
    net_id = board.nets.get(net_name)
    for node in board.raw:
        if not (isinstance(node, list) and node and node[0] == "segment"):
            continue
        seg_layer = _node_value(node, "layer")
        if seg_layer is not None and seg_layer != route_layer:
            continue
        seg_net = _segment_net_id(node)
        if net_id is not None and seg_net == net_id:
            continue
        points = _segment_points(node)
        if points is None:
            continue
        seg_margin = (
            _point_to_segment_distance((x, y), points[0], points[1])
            - probe_radius
            - _segment_width(node) / 2
            - min_clearance
        )
        margin = min(margin, seg_margin)

    return margin


def validate_all_probes(
    probes: list[tuple[float, float, str]],
    board: Board,
    constraints: Constraints,
    probe_cfg: ProbeConfig,
) -> CheckResult:
    result = CheckResult()
    placed: list[tuple[float, float]] = []
    for x, y, net_name in probes:
        single = check_placement(
            x, y, board, constraints, probe_cfg, placed, net_name=net_name,
        )
        for v in single.violations:
            v.message = f"[{net_name}] {v.message}"
            result.add(v)
        placed.append((x, y))
    return result


def _check_board_edge(
    x: float, y: float, board: Board, min_dist: float, result: CheckResult,
) -> None:
    if not board.contains_point(x, y):
        return
    dist = board.distance_to_outline(x, y)
    if dist < min_dist:
        result.add(Violation(
            rule="board_edge_clearance",
            message=f"Probe at ({x:.2f}, {y:.2f}) is {dist:.2f}mm from board edge "
                    f"(min {min_dist:.2f}mm)",
            x=x, y=y,
        ))


def _check_inside_board(x: float, y: float, board: Board, result: CheckResult) -> None:
    if not board.contains_point(x, y):
        result.add(Violation(
            rule="outside_board",
            message=f"Probe at ({x:.2f}, {y:.2f}) is outside the board outline",
            x=x, y=y,
        ))


def _check_component_collision(
    x: float,
    y: float,
    pad_diameter: float,
    min_clearance: float,
    board: Board,
    result: CheckResult,
) -> None:
    probe_radius = pad_diameter / 2
    clearance_radius = probe_radius + min_clearance
    for fp in board.footprints:
        # Skip generated protection components — their placement is managed by the engine
        if fp.ref.startswith(("TP", "R", "D", "FB", "RF")):
            continue
        fp_bounds = board.footprint_bounds(fp)
        expanded = BoundingBox(
            fp_bounds.min_x - clearance_radius,
            fp_bounds.min_y - clearance_radius,
            fp_bounds.max_x + clearance_radius,
            fp_bounds.max_y + clearance_radius,
        )
        if not expanded.contains(x, y):
            continue
        for pad in fp.pads:
            if _probe_intersects_pad(x, y, clearance_radius, pad):
                result.add(Violation(
                    rule="component_collision",
                    message=(
                        f"Probe at ({x:.2f}, {y:.2f}) violates "
                        f"{min_clearance:.2f}mm clearance to {fp.ref} pad {pad.number}"
                    ),
                    x=x, y=y,
                ))
                return


def _check_track_collision(
    x: float,
    y: float,
    pad_diameter: float,
    min_clearance: float,
    board: Board,
    side: str,
    net_name: str,
    result: CheckResult,
) -> None:
    route_layer = "F.Cu" if side == "top" else "B.Cu"
    net_id = board.nets.get(net_name)
    probe_radius = pad_diameter / 2
    for node in board.raw:
        if not (isinstance(node, list) and node and node[0] == "segment"):
            continue
        seg_layer = _node_value(node, "layer")
        if seg_layer is not None and seg_layer != route_layer:
            continue
        seg_net = _segment_net_id(node)
        if net_id is not None and seg_net == net_id:
            continue
        points = _segment_points(node)
        if points is None:
            continue
        clearance = (
            _point_to_segment_distance((x, y), points[0], points[1])
            - probe_radius
            - _segment_width(node) / 2
        )
        if clearance < min_clearance:
            result.add(Violation(
                rule="track_clearance",
                message=(
                    f"Probe at ({x:.2f}, {y:.2f}) violates "
                    f"{min_clearance:.2f}mm clearance to an existing track"
                ),
                x=x,
                y=y,
            ))
            return


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


def _effective_min_clearance(constraints: Constraints) -> float:
    return max(
        constraints.manufacturing.min_clearance_mm,
        constraints.routing.min_clearance_mm,
    )


def _segment_points(node: list) -> tuple[tuple[float, float], tuple[float, float]] | None:
    start = _find_node(node, "start")
    end = _find_node(node, "end")
    if start is None or end is None or len(start) < 3 or len(end) < 3:
        return None
    return (float(start[1]), float(start[2])), (float(end[1]), float(end[2]))


def _segment_net_id(node: list) -> int | None:
    raw_net = _node_value(node, "net")
    if raw_net is None:
        return None
    try:
        return int(raw_net)
    except ValueError:
        return None


def _segment_width(node: list) -> float:
    raw_width = _node_value(node, "width")
    if raw_width is None:
        return 0.15
    try:
        return float(raw_width)
    except ValueError:
        return 0.15


def _node_value(node: list, key: str) -> str | None:
    child = _find_node(node, key)
    if child is None or len(child) < 2:
        return None
    return str(child[1])


def _find_node(node: list, key: str) -> list | None:
    for child in node[1:]:
        if isinstance(child, list) and child and child[0] == key:
            return child
    return None


def _point_to_segment_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    px, py = point
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - sx, py - sy)
    t = max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / length_sq))
    closest_x = sx + t * dx
    closest_y = sy + t * dy
    return math.hypot(px - closest_x, py - closest_y)


def _probe_pad_clearance(x: float, y: float, probe_radius: float, pad: Pad) -> float:
    if pad.width <= 0 or pad.height <= 0:
        return float("inf")

    shape = pad.shape.lower()
    local_x, local_y = _to_pad_local(x, y, pad)

    if shape == "circle" and abs(pad.width - pad.height) < 1e-9:
        return math.hypot(local_x, local_y) - pad.width / 2 - probe_radius

    if shape == "oval":
        return _circle_to_capsule_clearance(
            local_x, local_y, probe_radius, pad.width, pad.height,
        )

    return _circle_to_rect_clearance(
        local_x, local_y, probe_radius, pad.width, pad.height,
    )


def _probe_intersects_pad(x: float, y: float, probe_radius: float, pad: Pad) -> bool:
    if pad.width <= 0 or pad.height <= 0:
        return False

    shape = pad.shape.lower()
    local_x, local_y = _to_pad_local(x, y, pad)

    if shape == "circle" and abs(pad.width - pad.height) < 1e-9:
        return math.hypot(local_x, local_y) <= pad.width / 2 + probe_radius

    if shape == "oval":
        return _circle_intersects_capsule(
            local_x, local_y, probe_radius, pad.width, pad.height,
        )

    return _circle_intersects_rect(
        local_x, local_y, probe_radius, pad.width, pad.height,
    )


def _to_pad_local(x: float, y: float, pad: Pad) -> tuple[float, float]:
    dx = x - pad.x
    dy = y - pad.y
    rad = math.radians(pad.rotation)
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)
    return dx * cos_r - dy * sin_r, dx * sin_r + dy * cos_r


def _circle_to_rect_clearance(
    x: float, y: float, radius: float, width: float, height: float,
) -> float:
    half_w = width / 2
    half_h = height / 2
    outside_x = max(abs(x) - half_w, 0.0)
    outside_y = max(abs(y) - half_h, 0.0)
    outside_dist = math.hypot(outside_x, outside_y)
    if outside_dist > 0:
        return outside_dist - radius
    inside_depth = min(half_w - abs(x), half_h - abs(y))
    return -inside_depth - radius


def _circle_intersects_rect(
    x: float, y: float, radius: float, width: float, height: float,
) -> bool:
    half_w = width / 2
    half_h = height / 2
    closest_x = max(-half_w, min(x, half_w))
    closest_y = max(-half_h, min(y, half_h))
    return math.hypot(x - closest_x, y - closest_y) <= radius


def _circle_to_capsule_clearance(
    x: float, y: float, radius: float, width: float, height: float,
) -> float:
    if width >= height:
        cap_radius = height / 2
        half_segment = max((width - height) / 2, 0.0)
        closest_x = max(-half_segment, min(x, half_segment))
        closest_y = 0.0
    else:
        cap_radius = width / 2
        half_segment = max((height - width) / 2, 0.0)
        closest_x = 0.0
        closest_y = max(-half_segment, min(y, half_segment))
    return math.hypot(x - closest_x, y - closest_y) - cap_radius - radius


def _circle_intersects_capsule(
    x: float, y: float, radius: float, width: float, height: float,
) -> bool:
    if width >= height:
        cap_radius = height / 2
        half_segment = max((width - height) / 2, 0.0)
        closest_x = max(-half_segment, min(x, half_segment))
        closest_y = 0.0
    else:
        cap_radius = width / 2
        half_segment = max((height - width) / 2, 0.0)
        closest_x = 0.0
        closest_y = max(-half_segment, min(y, half_segment))
    return math.hypot(x - closest_x, y - closest_y) <= cap_radius + radius
