from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Pad:
    number: str
    pad_type: str = "smd"
    shape: str = "circle"
    x: float = 0.0
    y: float = 0.0
    width: float = 1.0
    height: float = 1.0
    drill: float = 0.0
    net_name: str = ""
    net_id: int = 0
    layers: list[str] = field(default_factory=list)
    local_x: float = 0.0
    local_y: float = 0.0
    rotation: float = 0.0


@dataclass
class Footprint:
    ref: str
    value: str = ""
    lib_id: str = ""
    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0
    layer: str = "F.Cu"
    pads: list[Pad] = field(default_factory=list)
    uuid: str = ""


@dataclass
class EdgeSegment:
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass
class BoundingBox:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @property
    def center(self) -> tuple[float, float]:
        return (self.min_x + self.max_x) / 2, (self.min_y + self.max_y) / 2

    def contains(self, x: float, y: float) -> bool:
        return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y

    def inset(self, margin: float) -> BoundingBox:
        return BoundingBox(
            self.min_x + margin, self.min_y + margin,
            self.max_x - margin, self.max_y - margin,
        )

    def distance_to_edge(self, x: float, y: float) -> float:
        dx = max(self.min_x - x, 0, x - self.max_x)
        dy = max(self.min_y - y, 0, y - self.max_y)
        if self.contains(x, y):
            return min(x - self.min_x, self.max_x - x, y - self.min_y, self.max_y - y)
        return math.hypot(dx, dy)


@dataclass
class Board:
    footprints: list[Footprint] = field(default_factory=list)
    nets: dict[str, int] = field(default_factory=dict)
    edges: list[EdgeSegment] = field(default_factory=list)
    raw: list = field(default_factory=list)

    def net_names(self) -> list[str]:
        return [n for n in self.nets if n]

    def find_pads_by_net(self, net_name: str) -> list[tuple[Footprint, Pad]]:
        result = []
        for fp in self.footprints:
            for pad in fp.pads:
                if pad.net_name == net_name:
                    result.append((fp, pad))
        return result

    def next_net_id(self) -> int:
        return max(self.nets.values(), default=0) + 1

    def board_bounds(self) -> BoundingBox | None:
        if not self.edges:
            return None
        xs = []
        ys = []
        for e in self.edges:
            xs.extend([e.x1, e.x2])
            ys.extend([e.y1, e.y2])
        return BoundingBox(min(xs), min(ys), max(xs), max(ys))

    def outline_loops(self, tolerance: float = 1e-6) -> list[list[tuple[float, float]]]:
        """Return ordered Edge.Cuts loops, largest area first."""
        if len(self.edges) < 3:
            return []

        remaining = self.edges.copy()
        loops: list[list[tuple[float, float]]] = []

        while remaining:
            first = remaining.pop(0)
            points = [(first.x1, first.y1), (first.x2, first.y2)]

            while remaining:
                head = points[0]
                tail = points[-1]
                match_index = -1
                next_point: tuple[float, float] | None = None
                prepend = False

                for i, edge in enumerate(remaining):
                    start = (edge.x1, edge.y1)
                    end = (edge.x2, edge.y2)
                    if _points_close(tail, start, tolerance):
                        match_index = i
                        next_point = end
                        break
                    if _points_close(tail, end, tolerance):
                        match_index = i
                        next_point = start
                        break
                    if _points_close(head, end, tolerance):
                        match_index = i
                        next_point = start
                        prepend = True
                        break
                    if _points_close(head, start, tolerance):
                        match_index = i
                        next_point = end
                        prepend = True
                        break

                if next_point is None:
                    break

                remaining.pop(match_index)
                if prepend:
                    points.insert(0, next_point)
                else:
                    points.append(next_point)

                if len(points) >= 4 and _points_close(points[-1], points[0], tolerance):
                    points.pop()
                    break

            if len(points) >= 3:
                loops.append(points)

        loops.sort(key=lambda loop: abs(_polygon_area(loop)), reverse=True)
        return loops

    def outline_points(self, tolerance: float = 1e-6) -> list[tuple[float, float]]:
        """Return the primary board outline loop when Edge.Cuts can be chained."""
        loops = self.outline_loops(tolerance)
        return loops[0] if loops else []

    def contains_point(self, x: float, y: float, tolerance: float = 1e-6) -> bool:
        """Check containment against the board outline, falling back to bounds."""
        loops = self.outline_loops(tolerance)
        if not loops:
            bounds = self.board_bounds()
            return bounds.contains(x, y) if bounds else False

        for points in loops:
            for i, start in enumerate(points):
                end = points[(i + 1) % len(points)]
                if _point_to_segment_distance(x, y, start, end) <= tolerance:
                    return True

        if not _point_in_polygon(x, y, loops[0], tolerance):
            return False

        for cutout in loops[1:]:
            if _point_in_polygon(x, y, cutout, tolerance):
                return False

        return True

    def distance_to_outline(self, x: float, y: float) -> float:
        if not self.edges:
            return float("inf")
        return min(
            _point_to_segment_distance(x, y, (e.x1, e.y1), (e.x2, e.y2))
            for e in self.edges
        )

    def footprint_bounds(self, fp: Footprint) -> BoundingBox:
        if not fp.pads:
            return BoundingBox(fp.x - 1, fp.y - 1, fp.x + 1, fp.y + 1)
        boxes = [_pad_bounds(p) for p in fp.pads]
        return BoundingBox(
            min(b.min_x for b in boxes),
            min(b.min_y for b in boxes),
            max(b.max_x for b in boxes),
            max(b.max_y for b in boxes),
        )

    def all_pad_positions(self) -> list[tuple[float, float, str]]:
        result = []
        for fp in self.footprints:
            for pad in fp.pads:
                result.append((pad.x, pad.y, pad.net_name))
        return result


@dataclass
class Schematic:
    components: list = field(default_factory=list)
    labels: list = field(default_factory=list)
    wires: list = field(default_factory=list)
    raw: list = field(default_factory=list)

    def net_names(self) -> set[str]:
        return {lb["name"] for lb in self.labels}


def _point_in_polygon(
    x: float,
    y: float,
    points: list[tuple[float, float]],
    tolerance: float,
) -> bool:
    inside = False
    j = len(points) - 1
    for i, (xi, yi) in enumerate(points):
        xj, yj = points[j]
        if (yi > y) != (yj > y):
            cross_x = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x <= cross_x + tolerance:
                inside = not inside
        j = i
    return inside


def _polygon_area(points: list[tuple[float, float]]) -> float:
    area = 0.0
    for i, (x1, y1) in enumerate(points):
        x2, y2 = points[(i + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    return area / 2


def _points_close(
    a: tuple[float, float], b: tuple[float, float], tolerance: float,
) -> bool:
    return math.hypot(a[0] - b[0], a[1] - b[1]) <= tolerance


def _point_to_segment_distance(
    x: float,
    y: float,
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(x - sx, y - sy)
    t = max(0.0, min(1.0, ((x - sx) * dx + (y - sy) * dy) / length_sq))
    px = sx + t * dx
    py = sy + t * dy
    return math.hypot(x - px, y - py)


def _pad_bounds(pad: Pad) -> BoundingBox:
    if pad.shape == "circle" and abs(pad.width - pad.height) < 1e-9:
        radius = pad.width / 2
        return BoundingBox(
            pad.x - radius, pad.y - radius,
            pad.x + radius, pad.y + radius,
        )

    half_w = pad.width / 2
    half_h = pad.height / 2
    rad = math.radians(pad.rotation)
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)
    xs: list[float] = []
    ys: list[float] = []
    for lx, ly in (
        (-half_w, -half_h),
        (half_w, -half_h),
        (half_w, half_h),
        (-half_w, half_h),
    ):
        xs.append(pad.x + lx * cos_r + ly * sin_r)
        ys.append(pad.y - lx * sin_r + ly * cos_r)
    return BoundingBox(min(xs), min(ys), max(xs), max(ys))
