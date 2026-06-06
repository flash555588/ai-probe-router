"""Write testpoint symbols and net labels into a .kicad_sch s-expression tree."""

from __future__ import annotations

import uuid as _uuid
from pathlib import Path

from ...models.board import Schematic
from ...solvers.pin_mapper import PinAssignment
from ..kicad.sexpr import serialize

_TESTPOINT_LIB_SYMBOL = [
    "symbol", "Connector:TestPoint",
    ["pin_names", ["offset", "0.762"], "hide"],
    ["in_bom", "yes"],
    ["on_board", "yes"],
    ["symbol", "TestPoint_0_1",
     ["circle",
      ["center", "0", "-1.27"],
      ["radius", "0.635"],
      ["stroke", ["width", "0.1524"], ["type", "default"]],
      ["fill", ["type", "none"]]]],
    ["symbol", "TestPoint_1_1",
     ["pin", "passive", "line",
      ["at", "0", "0", "90"],
      ["length", "0"],
      ["name", "1", ["effects", ["font", ["size", "1.27", "1.27"]]]],
      ["number", "1", ["effects", ["font", ["size", "1.27", "1.27"]]]]]],
]


def add_testpoint_symbol(
    sch: Schematic,
    net_name: str,
    x: float,
    y: float,
    *,
    ref: str = "TP?",
) -> None:
    _ensure_lib_symbol(sch)
    uid = str(_uuid.uuid4())
    symbol_node = [
        "symbol",
        ["lib_id", "Connector:TestPoint"],
        ["at", str(x), str(y), "0"],
        ["unit", "1"],
        ["exclude_from_sim", "no"],
        ["in_bom", "yes"],
        ["on_board", "yes"],
        ["dnp", "no"],
        ["uuid", uid],
        ["property", "Reference", ref,
         ["at", str(x + 1.27), str(y - 1.27), "0"],
         ["effects", ["font", ["size", "1.27", "1.27"]]]],
        ["property", "Value", f"TP_{net_name}",
         ["at", str(x + 1.27), str(y + 1.27), "0"],
         ["effects", ["font", ["size", "1.27", "1.27"]]]],
        ["pin", "1", ["uuid", str(_uuid.uuid4())]],
    ]
    label_uid = str(_uuid.uuid4())
    label_node = [
        "label", net_name,
        ["at", str(x), str(y + 2.54), "0"],
        ["effects", ["font", ["size", "1.27", "1.27"]]],
        ["uuid", label_uid],
    ]
    wire_node = [
        "wire",
        ["pts", ["xy", str(x), str(y)], ["xy", str(x), str(y + 2.54)]],
        ["stroke", ["width", "0"], ["type", "default"]],
        ["uuid", str(_uuid.uuid4())],
    ]
    sch.raw.append(symbol_node)
    sch.raw.append(wire_node)
    sch.raw.append(label_node)


def add_connector_symbol(
    sch: Schematic,
    assignments: list[PinAssignment],
    *,
    ref: str = "J?",
    x: float = 50.0,
    y: float = 50.0,
    rows: int = 2,
    pins_per_row: int = 20,
) -> None:
    """Add a Connector_Generic symbol with labeled pins for each assignment."""
    _ensure_connector_lib_symbol(sch, rows, pins_per_row)
    lib_id = f"Connector_Generic:Conn_{rows:02d}x{pins_per_row:02d}_Counter_Clockwise"
    uid = str(_uuid.uuid4())

    symbol_node = [
        "symbol",
        ["lib_id", lib_id],
        ["at", str(x), str(y), "0"],
        ["unit", "1"],
        ["exclude_from_sim", "no"],
        ["in_bom", "yes"],
        ["on_board", "yes"],
        ["dnp", "no"],
        ["uuid", uid],
        ["property", "Reference", ref,
         ["at", str(x + 1.27), str(y - 1.27), "0"],
         ["effects", ["font", ["size", "1.27", "1.27"]]]],
        ["property", "Value", f"CONN_{ref}",
         ["at", str(x + 1.27), str(y + 1.27), "0"],
         ["effects", ["font", ["size", "1.27", "1.27"]]]],
    ]

    # Add pin entries for each assigned net
    for a in assignments:
        pin_uid = str(_uuid.uuid4())
        symbol_node.append(
            ["pin", str(a.pin_index + 1), ["uuid", pin_uid]]
        )

    sch.raw.append(symbol_node)

    # Add global labels for each assigned net (so wires can connect)
    for i, a in enumerate(assignments):
        label_y = y + i * 2.54
        label_node = [
            "global_label", a.net_name,
            ["shape", "input"],
            ["at", str(x + 5.08), str(label_y), "0"],
            ["effects", ["font", ["size", "1.27", "1.27"]]],
            ["uuid", str(_uuid.uuid4())],
        ]
        wire_node = [
            "wire",
            ["pts", ["xy", str(x + 2.54), str(label_y)], ["xy", str(x + 5.08), str(label_y)]],
            ["stroke", ["width", "0"], ["type", "default"]],
            ["uuid", str(_uuid.uuid4())],
        ]
        sch.raw.append(wire_node)
        sch.raw.append(label_node)


def _ensure_lib_symbol(sch: Schematic) -> None:
    for node in sch.raw[1:]:
        if isinstance(node, list) and node[0] == "lib_symbols":
            for child in node[1:]:
                if (
                    isinstance(child, list)
                    and child[0] == "symbol"
                    and len(child) > 1
                    and child[1] == "Connector:TestPoint"
                ):
                    return
            node.append(_TESTPOINT_LIB_SYMBOL)
            return
    sch.raw.append(["lib_symbols", _TESTPOINT_LIB_SYMBOL])


def _ensure_connector_lib_symbol(
    sch: Schematic, rows: int, pins_per_row: int,
) -> None:
    lib_id = f"Connector_Generic:Conn_{rows:02d}x{pins_per_row:02d}_Counter_Clockwise"
    for node in sch.raw[1:]:
        if isinstance(node, list) and node[0] == "lib_symbols":
            for child in node[1:]:
                if (
                    isinstance(child, list)
                    and child[0] == "symbol"
                    and len(child) > 1
                    and child[1] == lib_id
                ):
                    return
            # Minimal stub symbol — KiCad will resolve from library on load
            node.append([
                "symbol", lib_id,
                ["pin_names", ["offset", "1.016"], "hide"],
                ["in_bom", "yes"],
                ["on_board", "yes"],
            ])
            return
    sch.raw.append(["lib_symbols", [
        "symbol", lib_id,
        ["pin_names", ["offset", "1.016"], "hide"],
        ["in_bom", "yes"],
        ["on_board", "yes"],
    ]])


def write_schematic(sch: Schematic, path: str | Path) -> None:
    text = serialize(sch.raw)
    Path(path).write_text(text, encoding="utf-8")
