"""Write testpoint footprints and net declarations into a .kicad_pcb s-expression tree."""

from __future__ import annotations

import uuid as _uuid
from pathlib import Path

from ...models.board import Board
from ...solvers.pin_mapper import PinAssignment
from ..kicad.sexpr import serialize


def add_testpoint_footprint(
    board: Board,
    net_name: str,
    x: float,
    y: float,
    *,
    ref: str = "TP?",
    pad_diameter: float = 1.5,
    side: str = "top",
    label: str = "",
) -> None:
    net_id = board.nets.get(net_name)
    if net_id is None:
        net_id = board.next_net_id()
        board.nets[net_name] = net_id
        board.raw.append(["net", str(net_id), net_name])

    layer = "F.Cu" if side == "top" else "B.Cu"
    silk = "F.SilkS" if side == "top" else "B.SilkS"
    fab = "F.Fab" if side == "top" else "B.Fab"
    mask = "F.Mask" if side == "top" else "B.Mask"
    uid = str(_uuid.uuid4())

    fp_node = [
        "footprint", "TestPoint:TestPoint_Pad_D{:.1f}mm".format(pad_diameter),
        ["layer", layer],
        ["uuid", uid],
        ["at", str(x), str(y)],
        ["property", "Reference", ref,
         ["at", str(x), str(y - 2), "0"],
         ["layer", silk],
         ["effects", ["font", ["size", "1", "1"], ["thickness", "0.15"]]]],
        ["property", "Value", label or f"TP_{net_name}",
         ["at", str(x), str(y + 2), "0"],
         ["layer", fab],
         ["effects", ["font", ["size", "1", "1"], ["thickness", "0.15"]]]],
        ["pad", "1", "smd", "circle",
         ["at", "0", "0"],
         ["size", str(pad_diameter), str(pad_diameter)],
         ["layers", layer, mask],
         ["net", str(net_id), net_name]],
    ]
    board.raw.append(fp_node)


def add_connector_footprint(
    board: Board,
    assignments: list[PinAssignment],
    *,
    ref: str = "J?",
    x: float = 150.0,
    y: float = 100.0,
    rows: int = 2,
    pins_per_row: int = 20,
    pitch: float = 2.54,
    side: str = "top",
) -> None:
    """Add a PinHeader footprint for the development-board connector."""
    layer = "F.Cu" if side == "top" else "B.Cu"
    silk = "F.SilkS" if side == "top" else "B.SilkS"
    fab = "F.Fab" if side == "top" else "B.Fab"
    mask = "F.Mask" if side == "top" else "B.Mask"
    uid = str(_uuid.uuid4())
    total = rows * pins_per_row

    lib_name = f"Connector_PinHeader_2.54mm:PinHeader_{rows}x{pins_per_row}_P2.54mm_Vertical"

    fp_node: list = [
        "footprint", lib_name,
        ["layer", layer],
        ["uuid", uid],
        ["at", str(x), str(y)],
        ["property", "Reference", ref,
         ["at", str(x), str(y - 3), "0"],
         ["layer", silk],
         ["effects", ["font", ["size", "1", "1"], ["thickness", "0.15"]]]],
        ["property", "Value", f"CONN_{ref}",
         ["at", str(x), str(y + 3), "0"],
         ["layer", fab],
         ["effects", ["font", ["size", "1", "1"], ["thickness", "0.15"]]]],
    ]

    # Generate pads for each assigned pin
    for a in assignments:
        pad_num = str(a.pin_index + 1)
        row = a.pin_index // pins_per_row
        col = a.pin_index % pins_per_row
        px = col * pitch
        py = row * pitch

        net_id = board.nets.get(a.net_name)
        if net_id is None:
            net_id = board.next_net_id()
            board.nets[a.net_name] = net_id
            board.raw.append(["net", str(net_id), a.net_name])

        pad_node = [
            "pad", pad_num, "thru_hole", "circle",
            ["at", str(px), str(py)],
            ["size", "1.7", "1.7"],
            ["drill", "1.0"],
            ["layers", "*.Cu", mask],
            ["net", str(net_id), a.net_name],
        ]
        fp_node.append(pad_node)

    # Fill remaining unassigned pads with no-connect
    assigned_indices = {a.pin_index for a in assignments}
    for i in range(total):
        if i in assigned_indices:
            continue
        row = i // pins_per_row
        col = i % pins_per_row
        px = col * pitch
        py = row * pitch
        pad_node = [
            "pad", str(i + 1), "thru_hole", "circle",
            ["at", str(px), str(py)],
            ["size", "1.7", "1.7"],
            ["drill", "1.0"],
            ["layers", "*.Cu", mask],
        ]
        fp_node.append(pad_node)

    board.raw.append(fp_node)


def write_pcb(board: Board, path: str | Path) -> None:
    text = serialize(board.raw)
    Path(path).write_text(text, encoding="utf-8")
