"""Import a Specctra/Electra SES session file into a Board."""

from __future__ import annotations

from pathlib import Path

from ..eda_adapters.kicad.sexpr import parse
from ..models.board import Board


def import_ses(board: Board, path: str | Path) -> None:
    """Read an SES file and append routed tracks/vias to the board raw tree."""
    text = Path(path).read_text(encoding="utf-8")
    tree = parse(text)
    if not isinstance(tree, list) or tree[0] != "session":
        return

    route = _find_child(tree, "route")
    if not isinstance(route, list):
        return

    for net_node in route[1:]:
        if not isinstance(net_node, list) or net_node[0] != "net":
            continue
        for child in net_node[1:]:
            if not isinstance(child, list):
                continue
            if child[0] == "wire":
                _import_wire(board, child)
            elif child[0] == "via":
                _import_via(board, child)


def _import_wire(board: Board, wire_node: list) -> None:
    for child in wire_node[1:]:
        if not isinstance(child, list) or child[0] != "path":
            continue
        if len(child) < 4:
            continue
        layer = _layer_name(str(child[1]))
        try:
            width = float(child[2])
        except ValueError:
            continue
        nums = [float(n) for n in child[3:] if isinstance(n, str)]
        if len(nums) < 4 or len(nums) % 2 != 0:
            continue
        coords = [(nums[i] / 1000, nums[i + 1] / 1000) for i in range(0, len(nums), 2)]
        for i in range(len(coords) - 1):
            x1, y1 = coords[i]
            x2, y2 = coords[i + 1]
            seg = [
                "segment",
                ["start", str(x1), str(y1)],
                ["end", str(x2), str(y2)],
                ["width", str(width / 1000)],
                ["layer", layer],
                ["net", "0"],
                ["uuid", _new_uuid()],
            ]
            board.raw.append(seg)


def _import_via(board: Board, via_node: list) -> None:
    xy = _find_child(via_node, "xy")
    if not isinstance(xy, list) or len(xy) < 3:
        return
    try:
        x = float(xy[1]) / 1000
        y = float(xy[2]) / 1000
    except ValueError:
        return
    via_via = _find_child(via_node, "via_via")
    layers = ["F.Cu", "B.Cu"]
    if isinstance(via_via, list) and len(via_via) >= 2:
        layer_names = [str(n) for n in via_via[1:] if isinstance(n, str)]
        if layer_names:
            layers = [_layer_name(n) for n in layer_names]
    via_node_kicad = [
        "via",
        ["at", str(x), str(y)],
        ["size", "0.8"],
        ["drill", "0.4"],
        ["layers"] + layers,
        ["net", "0"],
        ["uuid", _new_uuid()],
    ]
    board.raw.append(via_node_kicad)


def _find_child(node: list, name: str) -> list | None:
    for child in node[1:]:
        if isinstance(child, list) and child and child[0] == name:
            return child
    return None


def _layer_name(ses_layer: str) -> str:
    mapping = {
        "TOP": "F.Cu",
        "BOTTOM": "B.Cu",
        "signal": "F.Cu",
    }
    return mapping.get(ses_layer, ses_layer)


def _new_uuid() -> str:
    import uuid
    return str(uuid.uuid4())
