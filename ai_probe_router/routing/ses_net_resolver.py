"""Resolve routed SES geometry into net-aware route objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..eda_adapters.kicad.sexpr import parse


class SesNetResolutionError(ValueError):
    """Raised when SES route geometry cannot be assigned to a valid net context."""


@dataclass(frozen=True)
class RoutedSegment:
    net_name: str
    layer: str
    x1_mm: float
    y1_mm: float
    x2_mm: float
    y2_mm: float
    width_mm: float


@dataclass(frozen=True)
class RoutedVia:
    net_name: str
    x_mm: float
    y_mm: float
    drill_mm: float | None = None
    diameter_mm: float | None = None
    layers: tuple[str, ...] = ("TOP", "BOTTOM")


@dataclass(frozen=True)
class RoutedSession:
    segments: list[RoutedSegment] = field(default_factory=list)
    vias: list[RoutedVia] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_ses_routes(path: str | Path) -> RoutedSession:
    """Read an SES file and return net-aware routed geometry without mutating a board."""
    return parse_ses_routes_text(Path(path).read_text(encoding="utf-8"))


def parse_ses_routes_text(text: str) -> RoutedSession:
    tree = parse(text)
    if not isinstance(tree, list) or not tree or tree[0] != "session":
        raise SesNetResolutionError("SES file root must be a session")

    route = _find_child(tree, "route")
    if route is None:
        return RoutedSession(warnings=["SES session has no route block"])

    segments: list[RoutedSegment] = []
    vias: list[RoutedVia] = []
    warnings: list[str] = []

    for child in route[1:]:
        if not isinstance(child, list) or not child:
            continue
        tag = str(child[0])
        if tag == "net":
            net_name = _net_name(child)
            for item in child[2:]:
                if not isinstance(item, list) or not item:
                    continue
                item_tag = str(item[0])
                if item_tag == "wire":
                    segments.extend(_parse_wire(net_name, item))
                elif item_tag == "via":
                    vias.append(_parse_via(net_name, item))
                else:
                    warnings.append(f"Ignored SES item in net {net_name}: {item_tag}")
        elif tag in {"wire", "via"}:
            raise SesNetResolutionError(f"{tag} outside net block")
        else:
            warnings.append(f"Ignored SES route item: {tag}")

    return RoutedSession(segments=segments, vias=vias, warnings=warnings)


def _net_name(net_node: list) -> str:
    if len(net_node) < 2:
        raise SesNetResolutionError("missing net name")
    raw_name = net_node[1]
    if not isinstance(raw_name, str):
        raise SesNetResolutionError("net name must be a string")
    name = str(raw_name)
    if not name:
        raise SesNetResolutionError("empty net name")
    return name


def _parse_wire(net_name: str, wire_node: list) -> list[RoutedSegment]:
    segments: list[RoutedSegment] = []
    for child in wire_node[1:]:
        if not isinstance(child, list) or not child or child[0] != "path":
            continue
        if len(child) < 7:
            raise SesNetResolutionError(f"wire path for {net_name} has too few fields")
        layer = str(child[1])
        width_mm = _ses_unit_to_mm(child[2], f"wire width for {net_name}")
        coords = [
            _ses_unit_to_mm(value, f"wire coordinate for {net_name}")
            for value in child[3:]
        ]
        if len(coords) < 4 or len(coords) % 2 != 0:
            raise SesNetResolutionError(f"wire path for {net_name} has invalid coordinate pairs")
        points = [
            (coords[index], coords[index + 1])
            for index in range(0, len(coords), 2)
        ]
        for start, end in zip(points, points[1:]):
            segments.append(
                RoutedSegment(
                    net_name=net_name,
                    layer=layer,
                    x1_mm=start[0],
                    y1_mm=start[1],
                    x2_mm=end[0],
                    y2_mm=end[1],
                    width_mm=width_mm,
                )
            )
    return segments


def _parse_via(net_name: str, via_node: list) -> RoutedVia:
    xy = _find_child(via_node, "xy")
    if xy is None or len(xy) < 3:
        raise SesNetResolutionError(f"via for {net_name} is missing xy")

    via_via = _find_child(via_node, "via_via")
    layers = ("TOP", "BOTTOM")
    if via_via is not None and len(via_via) > 1:
        layers = tuple(str(layer) for layer in via_via[1:] if isinstance(layer, str))

    return RoutedVia(
        net_name=net_name,
        x_mm=_ses_unit_to_mm(xy[1], f"via x for {net_name}"),
        y_mm=_ses_unit_to_mm(xy[2], f"via y for {net_name}"),
        layers=layers,
    )


def _find_child(node: list, name: str) -> list | None:
    for child in node[1:]:
        if isinstance(child, list) and child and child[0] == name:
            return child
    return None


def _ses_unit_to_mm(value, label: str) -> float:
    try:
        return float(value) / 1000
    except (TypeError, ValueError) as exc:
        raise SesNetResolutionError(f"invalid {label}: {value}") from exc
