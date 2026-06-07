"""Module-aware coarse routing corridor feasibility analysis."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

from ..models.board import Board, BoundingBox
from ..models.design_graph import RoutingStrategy
from ..models.module_graph import ModuleGraph, ModuleInstance

CorridorEndpoint = tuple[
    ModuleInstance,
    ModuleInstance | tuple[str, tuple[float, float]],
    str,
]


@dataclass
class RoutingCorridor:
    source_id: str
    target_id: str
    reason: str
    points: list[tuple[float, float]] = field(default_factory=list)
    length_mm: float = 0.0
    estimated_vias: int = 0
    congestion_score: float = 0.0
    sensitive_penalty: float = 0.0
    total_cost: float = 0.0
    ok: bool = True
    message: str = ""


@dataclass
class RoutingFeasibilityResult:
    skipped: bool = False
    skip_reason: str = ""
    corridors: list[RoutingCorridor] = field(default_factory=list)
    congestion_hotspots: list[tuple[float, float, int]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.skipped and all(c.ok for c in self.corridors)


def analyze_routing_feasibility(
    board: Board | None,
    graph: ModuleGraph,
    strategy: RoutingStrategy,
) -> RoutingFeasibilityResult:
    result = RoutingFeasibilityResult()
    if board is None:
        result.skipped = True
        result.skip_reason = "no_board"
        return result

    bounds = board.board_bounds()
    if bounds is None:
        result.skipped = True
        result.skip_reason = "no_board_outline"
        return result

    if any(instance.region is None for instance in graph.instances):
        _assign_regions(graph, bounds)
    endpoints = _corridor_endpoints(graph, bounds)
    node_usage: dict[tuple[float, float], int] = {}

    for source, target, reason in endpoints:
        corridor = _route_corridor(board, source, target, reason, strategy)
        result.corridors.append(corridor)
        for point in corridor.points:
            node_usage[point] = node_usage.get(point, 0) + 1

    for corridor in result.corridors:
        corridor.congestion_score = sum(
            max(node_usage.get(point, 0) - 1, 0)
            for point in corridor.points
        )
        corridor.sensitive_penalty = _sensitive_penalty(graph, corridor, strategy)
        corridor.total_cost = (
            corridor.length_mm * strategy.length_weight
            + corridor.estimated_vias * strategy.via_weight
            + corridor.congestion_score * strategy.congestion_weight
            + corridor.sensitive_penalty
        )

    result.congestion_hotspots = sorted(
        (
            (x, y, count)
            for (x, y), count in node_usage.items()
            if count > 1
        ),
        key=lambda item: item[2],
        reverse=True,
    )[:10]
    if result.congestion_hotspots:
        result.warnings.append(
            f"{len(result.congestion_hotspots)} coarse routing congestion hotspots"
        )
    return result


def _assign_regions(graph: ModuleGraph, bounds: BoundingBox) -> None:
    count = max(len(graph.instances), 1)
    cols = max(1, math.ceil(math.sqrt(count)))
    rows = max(1, math.ceil(count / cols))
    cell_w = bounds.width / cols
    cell_h = bounds.height / rows

    for index, instance in enumerate(graph.instances):
        preferred = _preferred_center(instance, bounds)
        if preferred is None:
            col = index % cols
            row = index // cols
            preferred = (
                bounds.min_x + cell_w * (col + 0.5),
                bounds.min_y + cell_h * (row + 0.5),
            )

        side = max(math.sqrt(max(instance.area_mm2, 16.0)), 4.0)
        width = min(side, bounds.width / 2)
        height = min(side, bounds.height / 2)
        cx = min(max(preferred[0], bounds.min_x + width / 2), bounds.max_x - width / 2)
        cy = min(max(preferred[1], bounds.min_y + height / 2), bounds.max_y - height / 2)
        instance.region = BoundingBox(
            cx - width / 2,
            cy - height / 2,
            cx + width / 2,
            cy + height / 2,
        )


def _preferred_center(
    instance: ModuleInstance,
    bounds: BoundingBox,
) -> tuple[float, float] | None:
    region = instance.preferred_region.lower()
    if not region:
        if "power" in instance.module_type:
            region = "left"
        elif "debug" in instance.module_type:
            region = "right"
        elif "analog" in instance.module_type:
            region = "top"
        elif "communication" in instance.module_type or "can" in instance.module_type:
            region = "right"
    mapping = {
        "left": (bounds.min_x + bounds.width * 0.2, bounds.min_y + bounds.height * 0.5),
        "right": (bounds.min_x + bounds.width * 0.8, bounds.min_y + bounds.height * 0.5),
        "top": (bounds.min_x + bounds.width * 0.5, bounds.min_y + bounds.height * 0.2),
        "bottom": (bounds.min_x + bounds.width * 0.5, bounds.min_y + bounds.height * 0.8),
        "center": bounds.center,
        "power_input": (bounds.min_x + bounds.width * 0.15, bounds.min_y + bounds.height * 0.5),
        "probe_edge": (bounds.min_x + bounds.width * 0.5, bounds.min_y + bounds.height * 0.85),
    }
    return mapping.get(region)


def _corridor_endpoints(
    graph: ModuleGraph,
    bounds: BoundingBox,
) -> list[CorridorEndpoint]:
    by_id = graph.by_id()
    endpoints: list[CorridorEndpoint] = []
    seen: set[tuple[str, str, str]] = set()
    for dep in graph.dependencies:
        source = by_id.get(dep.source_id)
        target = by_id.get(dep.target_id)
        if source is None or target is None:
            continue
        key = (source.instance_id, target.instance_id, dep.reason)
        if not dep.directed:
            key = tuple(sorted((source.instance_id, target.instance_id))) + (dep.reason,)
        if key in seen:
            continue
        seen.add(key)
        endpoints.append((source, target, dep.reason))

    probe_target = ("PROBE", (bounds.min_x + bounds.width * 0.5, bounds.max_y))
    for instance in graph.instances:
        if instance.target_nets:
            endpoints.append((instance, probe_target, "probe_access"))
    return endpoints


def _route_corridor(
    board: Board,
    source: ModuleInstance,
    target: ModuleInstance | tuple[str, tuple[float, float]],
    reason: str,
    strategy: RoutingStrategy,
) -> RoutingCorridor:
    start = _instance_center(source)
    if isinstance(target, ModuleInstance):
        end = _instance_center(target)
        target_id = target.instance_id
    else:
        target_id, end = target

    path = _astar(board, start, end, strategy.coarse_grid_mm)
    if not path:
        return RoutingCorridor(
            source_id=source.instance_id,
            target_id=target_id,
            reason=reason,
            ok=False,
            message="coarse_corridor_not_found",
        )
    return RoutingCorridor(
        source_id=source.instance_id,
        target_id=target_id,
        reason=reason,
        points=path,
        length_mm=_path_length(path),
        estimated_vias=_bend_count(path),
    )


def _astar(
    board: Board,
    start: tuple[float, float],
    end: tuple[float, float],
    grid: float,
) -> list[tuple[float, float]]:
    bounds = board.board_bounds()
    if bounds is None:
        return []
    grid = max(grid, 0.5)
    min_ix = math.floor(bounds.min_x / grid)
    min_iy = math.floor(bounds.min_y / grid)
    max_ix = math.ceil(bounds.max_x / grid)
    max_iy = math.ceil(bounds.max_y / grid)

    def to_node(point: tuple[float, float]) -> tuple[int, int]:
        return round(point[0] / grid), round(point[1] / grid)

    def to_point(node: tuple[int, int]) -> tuple[float, float]:
        return round(node[0] * grid, 6), round(node[1] * grid, 6)

    start_node = to_node(start)
    end_node = to_node(end)
    open_heap: list[tuple[float, int, tuple[int, int]]] = [(0.0, 0, start_node)]
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score = {start_node: 0.0}
    closed: set[tuple[int, int]] = set()
    counter = 0

    while open_heap:
        _priority, _counter, current = heapq.heappop(open_heap)
        if current in closed:
            continue
        if current == end_node:
            route = [start]
            route.extend(to_point(n) for n in _reconstruct(came_from, current))
            route.append(end)
            return _compress(route)
        closed.add(current)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbor = (current[0] + dx, current[1] + dy)
            if neighbor in closed:
                continue
            if not (min_ix <= neighbor[0] <= max_ix and min_iy <= neighbor[1] <= max_iy):
                continue
            point = to_point(neighbor)
            if not board.contains_point(*point):
                continue
            tentative = g_score[current] + grid
            if tentative >= g_score.get(neighbor, float("inf")):
                continue
            came_from[neighbor] = current
            g_score[neighbor] = tentative
            counter += 1
            priority = tentative + _manhattan(neighbor, end_node) * grid
            heapq.heappush(open_heap, (priority, counter, neighbor))
    return []


def _instance_center(instance: ModuleInstance) -> tuple[float, float]:
    if instance.region is None:
        return (0.0, 0.0)
    return instance.region.center


def _path_length(points: list[tuple[float, float]]) -> float:
    return sum(
        math.hypot(b[0] - a[0], b[1] - a[1])
        for a, b in zip(points, points[1:])
    )


def _bend_count(points: list[tuple[float, float]]) -> int:
    if len(points) < 3:
        return 0
    bends = 0
    for a, b, c in zip(points, points[1:], points[2:]):
        if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1]):
            bends += 1
    return bends


def _sensitive_penalty(
    graph: ModuleGraph,
    corridor: RoutingCorridor,
    strategy: RoutingStrategy,
) -> float:
    source = graph.by_id().get(corridor.source_id)
    if source is None or not _is_sensitive(source):
        return 0.0
    penalty = 0.0
    for instance in graph.instances:
        if instance.instance_id == source.instance_id or not _is_noisy(instance):
            continue
        center = _instance_center(instance)
        if any(
            math.hypot(point[0] - center[0], point[1] - center[1])
            <= strategy.sensitive_net_spacing_mm
            for point in corridor.points
        ):
            penalty += strategy.sensitive_net_spacing_mm
    return penalty


def _is_sensitive(instance: ModuleInstance) -> bool:
    if any(h.hint_type == "sensitive_route" and h.supported for h in instance.ai_hints):
        return True
    return "analog" in instance.module_type or "rf" in instance.module_type


def _is_noisy(instance: ModuleInstance) -> bool:
    noisy_tokens = ("gpio", "power", "switching", "communication", "can", "rs485")
    return any(token in instance.module_type for token in noisy_tokens)


def _reconstruct(
    came_from: dict[tuple[int, int], tuple[int, int]],
    current: tuple[int, int],
) -> list[tuple[int, int]]:
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def _compress(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    deduped: list[tuple[float, float]] = []
    for point in points:
        if not deduped or point != deduped[-1]:
            deduped.append(point)
    if len(deduped) <= 2:
        return deduped
    result = [deduped[0]]
    for a, b, c in zip(deduped, deduped[1:], deduped[2:]):
        if (b[0] - a[0]) * (c[1] - b[1]) != (b[1] - a[1]) * (c[0] - b[0]):
            result.append(b)
    result.append(deduped[-1])
    return result


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
