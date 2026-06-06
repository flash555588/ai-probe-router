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

    def footprint_bounds(self, fp: Footprint) -> BoundingBox:
        if not fp.pads:
            return BoundingBox(fp.x - 1, fp.y - 1, fp.x + 1, fp.y + 1)
        xs = [p.x for p in fp.pads]
        ys = [p.y for p in fp.pads]
        margin = max(max(p.width, p.height) for p in fp.pads) / 2
        return BoundingBox(min(xs) - margin, min(ys) - margin,
                          max(xs) + margin, max(ys) + margin)

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
