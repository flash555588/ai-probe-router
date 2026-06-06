"""Import a Specctra/Electra SES session file into a Board."""

from __future__ import annotations

import re
from pathlib import Path

from ..models.board import Board


def import_ses(board: Board, path: str | Path) -> None:
    """Read an SES file and append routed tracks/vias to the board raw tree."""
    text = Path(path).read_text(encoding="utf-8")
    wires = _extract_wires(text)
    vias = _extract_vias(text)

    for layer, width_um, coords in wires:
        if len(coords) < 2:
            continue
        for i in range(len(coords) - 1):
            x1, y1 = coords[i]
            x2, y2 = coords[i + 1]
            seg = [
                "segment",
                ["start", str(x1), str(y1)],
                ["end", str(x2), str(y2)],
                ["width", str(width_um / 1000)],
                ["layer", layer],
                ["net", "0"],
                ["uuid", _new_uuid()],
            ]
            board.raw.append(seg)

    for x, y, layers in vias:
        via_node = [
            "via",
            ["at", str(x), str(y)],
            ["size", "0.8"],
            ["drill", "0.4"],
            ["layers"] + layers,
            ["net", "0"],
            ["uuid", _new_uuid()],
        ]
        board.raw.append(via_node)


def _extract_wires(text: str) -> list[tuple[str, float, list[tuple[float, float]]]]:
    results: list[tuple[str, float, list[tuple[float, float]]]] = []
    # Match (wire (path LAYER WIDTH x1 y1 x2 y2 ...))
    for m in re.finditer(
        r'\(wire\s+\(path\s+(\S+)\s+(\d+)\s+([^)]+)\)',
        text,
    ):
        layer = _layer_name(m.group(1))
        width = float(m.group(2))
        nums = [float(n) for n in m.group(3).split()]
        coords = [(nums[i] / 1000, nums[i + 1] / 1000) for i in range(0, len(nums), 2)]
        results.append((layer, width, coords))
    return results


def _extract_vias(text: str) -> list[tuple[float, float, list[str]]]:
    results: list[tuple[float, float, list[str]]] = []
    for m in re.finditer(
        r'\(via\s+\(xy\s+(\d+)\s+(\d+)\)\s+\(via_via\s+([^)]+)\)',
        text,
    ):
        x = float(m.group(1)) / 1000
        y = float(m.group(2)) / 1000
        layers = ["F.Cu", "B.Cu"]
        results.append((x, y, layers))
    return results


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
