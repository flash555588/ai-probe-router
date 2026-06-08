"""Grid/A* electrical router with pad, track, and board keepouts."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

from ..models.board import Board, Pad, _pad_bounds


@dataclass
class RouteResult:
    ok: bool
    points: list[tuple[float, float]]
    reason: str = ""


@dataclass(frozen=True)
class _PadKeepout:
    pad: Pad
    radius: float


@dataclass(frozen=True)
class _TrackKeepout:
    start: tuple[float, float]
    end: tuple[float, float]
    radius: float


def route_grid(
    board: Board,
    net_name: str,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    width: float,
    side: str = "top",
    clearance: float = 0.20,
    grid: float = 0.5,
    max_expansions: int = 60000,
) -> RouteResult:
    """Route a single-net connection on a board-aligned grid."""
    if _points_close(start, end):
        return RouteResult(True, [start, end])

    bounds = board.board_bounds()
    if bounds is None:
        return RouteResult(False, [], "no_board_outline")

    grid = max(grid, width, 0.10)
    route_layer = "F.Cu" if side == "top" else "B.Cu"
    pads = _pad_keepouts(board, net_name, width, clearance, route_layer)
    tracks = _track_keepouts(board, net_name, width, clearance, route_layer)

    if _segment_clear(board, start, end, pads, tracks, width, grid):
        return RouteResult(True, [start, end])

    min_ix = math.floor(bounds.min_x / grid) - 2
    min_iy = math.floor(bounds.min_y / grid) - 2
    max_ix = math.ceil(bounds.max_x / grid) + 2
    max_iy = math.ceil(bounds.max_y / grid) + 2

    def in_bounds(node: tuple[int, int]) -> bool:
        ix, iy = node
        return min_ix <= ix <= max_ix and min_iy <= iy <= max_iy

    def to_point(node: tuple[int, int]) -> tuple[float, float]:
        return round(node[0] * grid, 6), round(node[1] * grid, 6)

    start_node = _nearest_open_node(
        start, grid, in_bounds, to_point, board, pads, tracks, width,
    )
    end_node = _nearest_open_node(
        end, grid, in_bounds, to_point, board, pads, tracks, width,
    )
    if start_node is None:
        return RouteResult(False, [], "no_open_grid_node_near_start")
    if end_node is None:
        return RouteResult(False, [], "no_open_grid_node_near_end")

    if not _segment_clear(board, start, to_point(start_node), pads, tracks, width, grid):
        return RouteResult(False, [], "start_escape_blocked")
    if not _segment_clear(board, to_point(end_node), end, pads, tracks, width, grid):
        return RouteResult(False, [], "end_escape_blocked")

    path = _astar(
        start_node,
        end_node,
        in_bounds,
        to_point,
        board,
        pads,
        tracks,
        width,
        grid,
        max_expansions,
    )
    if not path:
        return RouteResult(False, [], "grid_route_not_found")

    route = [start]
    route.extend(to_point(node) for node in path)
    route.append(end)
    route = _dedupe_points(route)
    route = _compress_collinear(route)
    return RouteResult(True, route)


def _astar(
    start_node: tuple[int, int],
    end_node: tuple[int, int],
    in_bounds,
    to_point,
    board: Board,
    pads: list[_PadKeepout],
    tracks: list[_TrackKeepout],
    width: float,
    grid: float,
    max_expansions: int,
) -> list[tuple[int, int]]:
    open_heap: list[tuple[float, int, tuple[int, int]]] = []
    heapq.heappush(open_heap, (0.0, 0, start_node))
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score: dict[tuple[int, int], float] = {start_node: 0.0}
    closed: set[tuple[int, int]] = set()
    counter = 0
    expansions = 0

    neighbors = ((1, 0), (-1, 0), (0, 1), (0, -1))
    while open_heap and expansions < max_expansions:
        _f, _counter, current = heapq.heappop(open_heap)
        if current in closed:
            continue
        if current == end_node:
            return _reconstruct_path(came_from, current)

        closed.add(current)
        expansions += 1
        current_point = to_point(current)

        for dx, dy in neighbors:
            neighbor = (current[0] + dx, current[1] + dy)
            if neighbor in closed or not in_bounds(neighbor):
                continue
            neighbor_point = to_point(neighbor)
            if not _point_clear(board, neighbor_point, pads, tracks, width):
                continue
            if not _segment_clear(
                board, current_point, neighbor_point, pads, tracks, width, grid,
            ):
                continue
            tentative = g_score[current] + grid
            if tentative >= g_score.get(neighbor, float("inf")):
                continue
            came_from[neighbor] = current
            g_score[neighbor] = tentative
            counter += 1
            f_score = tentative + _manhattan(neighbor, end_node) * grid
            heapq.heappush(open_heap, (f_score, counter, neighbor))

    return []


def _nearest_open_node(
    point: tuple[float, float],
    grid: float,
    in_bounds,
    to_point,
    board: Board,
    pads: list[_PadKeepout],
    tracks: list[_TrackKeepout],
    width: float,
) -> tuple[int, int] | None:
    base = (round(point[0] / grid), round(point[1] / grid))
    best: tuple[int, int] | None = None
    best_dist = float("inf")
    for radius in range(0, 7):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) != radius:
                    continue
                node = (base[0] + dx, base[1] + dy)
                if not in_bounds(node):
                    continue
                node_point = to_point(node)
                if not _point_clear(board, node_point, pads, tracks, width):
                    continue
                dist = math.hypot(node_point[0] - point[0], node_point[1] - point[1])
                if dist < best_dist:
                    best = node
                    best_dist = dist
        if best is not None:
            return best
    return None


def _point_clear(
    board: Board,
    point: tuple[float, float],
    pads: list[_PadKeepout],
    tracks: list[_TrackKeepout],
    width: float,
) -> bool:
    x, y = point
    if not board.contains_point(x, y):
        return False
    if board.distance_to_outline(x, y) < width / 2:
        return False
    for pad in pads:
        if _point_to_pad_clearance(point, pad.pad) < pad.radius:
            return False
    for track in tracks:
        if _point_to_segment_distance(point, track.start, track.end) < track.radius:
            return False
    return True


def _segment_clear(
    board: Board,
    start: tuple[float, float],
    end: tuple[float, float],
    pads: list[_PadKeepout],
    tracks: list[_TrackKeepout],
    width: float,
    grid: float,
) -> bool:
    if not board.contains_point(*start) or not board.contains_point(*end):
        return False
    if _segment_crosses_outline(board, start, end):
        return False
    length = math.hypot(end[0] - start[0], end[1] - start[1])
    steps = max(1, math.ceil(length / max(grid / 2, width / 2, 0.05)))
    for i in range(1, steps):
        t = i / steps
        x = start[0] + (end[0] - start[0]) * t
        y = start[1] + (end[1] - start[1]) * t
        if not board.contains_point(x, y):
            return False
        if board.distance_to_outline(x, y) < width / 2:
            return False

    # Quick bounding-box rejection before expensive per-point clearance
    seg_min_x = min(start[0], end[0])
    seg_max_x = max(start[0], end[0])
    seg_min_y = min(start[1], end[1])
    seg_max_y = max(start[1], end[1])
    for pad in pads:
        pb = _pad_bounds(pad.pad)
        # Expand segment bbox by keepout radius; skip if no overlap
        r = pad.radius
        if pb.max_x < seg_min_x - r or pb.min_x > seg_max_x + r:
            continue
        if pb.max_y < seg_min_y - r or pb.min_y > seg_max_y + r:
            continue
        if _segment_to_pad_clearance(start, end, pad.pad, grid) < pad.radius:
            return False
    for track in tracks:
        if _segment_to_segment_distance(start, end, track.start, track.end) < track.radius:
            return False
    return True


def _segment_crosses_outline(
    board: Board,
    start: tuple[float, float],
    end: tuple[float, float],
) -> bool:
    for edge in board.edges:
        edge_start = (edge.x1, edge.y1)
        edge_end = (edge.x2, edge.y2)
        if _segments_intersect(start, end, edge_start, edge_end):
            if (
                _points_close(start, edge_start)
                or _points_close(start, edge_end)
                or _points_close(end, edge_start)
                or _points_close(end, edge_end)
            ):
                continue
            return True
    return False


def _pad_keepouts(
    board: Board,
    net_name: str,
    width: float,
    clearance: float,
    route_layer: str,
) -> list[_PadKeepout]:
    keepouts: list[_PadKeepout] = []
    for fp in board.footprints:
        for pad in fp.pads:
            if pad.net_name == net_name:
                continue
            if not _pad_on_layer(pad, route_layer):
                continue
            radius = width / 2 + clearance
            keepouts.append(_PadKeepout(pad, radius))
    return keepouts


def _track_keepouts(
    board: Board,
    net_name: str,
    width: float,
    clearance: float,
    route_layer: str,
) -> list[_TrackKeepout]:
    keepouts: list[_TrackKeepout] = []
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
        seg_width = _segment_width(node)
        radius = width / 2 + seg_width / 2 + clearance
        keepouts.append(_TrackKeepout(points[0], points[1], radius))
    return keepouts


def _pad_on_layer(pad: Pad, route_layer: str) -> bool:
    if not pad.layers:
        return True
    return route_layer in pad.layers or "*.Cu" in pad.layers


def _segment_to_pad_clearance(
    start: tuple[float, float],
    end: tuple[float, float],
    pad: Pad,
    grid: float,
) -> float:
    length = math.hypot(end[0] - start[0], end[1] - start[1])
    steps = max(1, math.ceil(length / min(grid / 2, 0.10)))
    return min(
        _point_to_pad_clearance(
            (
                start[0] + (end[0] - start[0]) * i / steps,
                start[1] + (end[1] - start[1]) * i / steps,
            ),
            pad,
        )
        for i in range(steps + 1)
    )


def _point_to_pad_clearance(point: tuple[float, float], pad: Pad) -> float:
    x, y = _to_pad_local(point, pad)
    shape = pad.shape.lower()
    if shape == "circle" and abs(pad.width - pad.height) < 1e-9:
        return math.hypot(x, y) - pad.width / 2
    if shape == "oval":
        return _point_to_capsule_clearance(x, y, pad.width, pad.height)
    return _point_to_rect_clearance(x, y, pad.width, pad.height)


def _to_pad_local(point: tuple[float, float], pad: Pad) -> tuple[float, float]:
    dx = point[0] - pad.x
    dy = point[1] - pad.y
    rad = math.radians(pad.rotation)
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)
    return dx * cos_r - dy * sin_r, dx * sin_r + dy * cos_r


def _point_to_rect_clearance(x: float, y: float, width: float, height: float) -> float:
    half_w = width / 2
    half_h = height / 2
    outside_x = max(abs(x) - half_w, 0.0)
    outside_y = max(abs(y) - half_h, 0.0)
    outside_dist = math.hypot(outside_x, outside_y)
    if outside_dist > 0:
        return outside_dist
    return -min(half_w - abs(x), half_h - abs(y))


def _point_to_capsule_clearance(x: float, y: float, width: float, height: float) -> float:
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
    return math.hypot(x - closest_x, y - closest_y) - cap_radius


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


def _reconstruct_path(
    came_from: dict[tuple[int, int], tuple[int, int]],
    current: tuple[int, int],
) -> list[tuple[int, int]]:
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def _dedupe_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    deduped: list[tuple[float, float]] = []
    for point in points:
        if not deduped or not _points_close(deduped[-1], point):
            deduped.append(point)
    return deduped


def _compress_collinear(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return points
    result = [points[0]]
    for i in range(1, len(points) - 1):
        prev = result[-1]
        current = points[i]
        nxt = points[i + 1]
        cross = (
            (current[0] - prev[0]) * (nxt[1] - current[1])
            - (current[1] - prev[1]) * (nxt[0] - current[0])
        )
        if abs(cross) > 1e-9:
            result.append(current)
    result.append(points[-1])
    return result


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


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


def _segment_to_segment_distance(
    a1: tuple[float, float],
    a2: tuple[float, float],
    b1: tuple[float, float],
    b2: tuple[float, float],
) -> float:
    if _segments_intersect(a1, a2, b1, b2):
        return 0.0
    return min(
        _point_to_segment_distance(a1, b1, b2),
        _point_to_segment_distance(a2, b1, b2),
        _point_to_segment_distance(b1, a1, a2),
        _point_to_segment_distance(b2, a1, a2),
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


def _points_close(
    a: tuple[float, float],
    b: tuple[float, float],
    tolerance: float = 1e-6,
) -> bool:
    return math.hypot(a[0] - b[0], a[1] - b[1]) <= tolerance
