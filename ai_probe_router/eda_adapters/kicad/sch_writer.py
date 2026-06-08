"""Write testpoint symbols, protection components, and labels into a schematic."""

from __future__ import annotations

import uuid as _uuid
from pathlib import Path

from ...models.board import Schematic
from ...models.module_graph import ModuleInstance
from ...models.protection import ProtectionComponent, ProtectionType
from ...solvers.pin_mapper import PinAssignment
from ..kicad.sch_health import repair_schematic_tree
from ..kicad.sexpr import QuotedStr, serialize


def _quoted(value: object) -> QuotedStr:
    """Return a KiCad string field value."""
    if isinstance(value, QuotedStr):
        return value
    return QuotedStr(str(value))


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
      ["name", QuotedStr("1"), ["effects", ["font", ["size", "1.27", "1.27"]]]],
      ["number", QuotedStr("1"), ["effects", ["font", ["size", "1.27", "1.27"]]]]]],
]

_RESISTOR_LIB_SYMBOL = [
    "symbol", "Device:R",
    ["pin_names", ["offset", "0"]],
    ["in_bom", "yes"],
    ["on_board", "yes"],
    ["symbol", "R_0_1",
     ["rectangle",
      ["start", "-1.016", "-2.54"],
      ["end", "1.016", "2.54"],
      ["stroke", ["width", "0.254"], ["type", "default"]],
      ["fill", ["type", "none"]]]],
    ["symbol", "R_1_1",
     ["pin", "passive", "line",
      ["at", "0", "3.81", "270"],
      ["length", "1.27"],
      ["name", "~", ["effects", ["font", ["size", "1.27", "1.27"]]]],
      ["number", QuotedStr("1"), ["effects", ["font", ["size", "1.27", "1.27"]]]]],
     ["pin", "passive", "line",
      ["at", "0", "-3.81", "90"],
      ["length", "1.27"],
      ["name", "~", ["effects", ["font", ["size", "1.27", "1.27"]]]],
      ["number", QuotedStr("2"), ["effects", ["font", ["size", "1.27", "1.27"]]]]]],
]

_FERRITE_LIB_SYMBOL = [
    "symbol", "Device:FerriteBead",
    ["pin_names", ["offset", "1.016"], "hide"],
    ["in_bom", "yes"],
    ["on_board", "yes"],
    ["symbol", "FerriteBead_0_1",
     ["polyline",
      ["pts",
       ["xy", "0", "-2.54"],
       ["xy", "0", "-1.905"],
       ["xy", "0.762", "-1.524"],
       ["xy", "-0.762", "-0.762"],
       ["xy", "0.762", "0"],
       ["xy", "-0.762", "0.762"],
       ["xy", "0.762", "1.524"],
       ["xy", "0", "1.905"],
       ["xy", "0", "2.54"]],
      ["stroke", ["width", "0"], ["type", "default"]],
      ["fill", ["type", "none"]]]],
    ["symbol", "FerriteBead_1_1",
     ["pin", "passive", "line",
      ["at", "0", "3.81", "270"],
      ["length", "1.27"],
      ["name", "~", ["effects", ["font", ["size", "1.27", "1.27"]]]],
      ["number", QuotedStr("1"), ["effects", ["font", ["size", "1.27", "1.27"]]]]],
     ["pin", "passive", "line",
      ["at", "0", "-3.81", "90"],
      ["length", "1.27"],
      ["name", "~", ["effects", ["font", ["size", "1.27", "1.27"]]]],
      ["number", QuotedStr("2"), ["effects", ["font", ["size", "1.27", "1.27"]]]]]],
]


def _make_probe_fields(
    x: float,
    y: float,
    role: str = "",
    required: bool = False,
    current_ma: float = 0.0,
    side: str = "top",
) -> list[list]:
    """Return KiCad property nodes for probe metadata fields."""
    fields: list[list] = []
    offset = 2.54
    if role:
        fields.append(
            ["property", _quoted("PROBE_ROLE"), _quoted(role),
             ["at", str(x + offset), str(y - offset), "0"],
             ["effects", ["font", ["size", "1.27", "1.27"]]]]
        )
    fields.append(
        ["property", _quoted("TEST_REQUIRED"), _quoted("yes" if required else "no"),
         ["at", str(x + offset), str(y - offset - 1.27), "0"],
         ["effects", ["font", ["size", "1.27", "1.27"]]]]
    )
    if current_ma > 0:
        fields.append(
            ["property", _quoted("CURRENT_LIMIT"), _quoted(f"{current_ma}mA"),
             ["at", str(x + offset), str(y - offset - 2.54), "0"],
             ["effects", ["font", ["size", "1.27", "1.27"]]]]
        )
    fields.append(
        ["property", _quoted("ACCESS_SIDE"), _quoted(side),
         ["at", str(x + offset), str(y - offset - 3.81), "0"],
         ["effects", ["font", ["size", "1.27", "1.27"]]]]
    )
    return fields

def add_testpoint_symbol(
    sch: Schematic,
    net_name: str,
    x: float,
    y: float,
    *,
    ref: str = "TP?",
    role: str = "",
    required: bool = False,
    current_ma: float = 0.0,
    side: str = "top",
) -> None:
    _ensure_lib_symbol(sch)
    uid = str(_uuid.uuid4())
    symbol_node = [
        "symbol",
        ["lib_id", _quoted("Connector:TestPoint")],
        ["at", str(x), str(y), "0"],
        ["unit", "1"],
        ["exclude_from_sim", "no"],
        ["in_bom", "yes"],
        ["on_board", "yes"],
        ["dnp", "no"],
        ["uuid", uid],
        ["property", _quoted("Reference"), _quoted(ref),
         ["at", str(x + 1.27), str(y - 1.27), "0"],
         ["effects", ["font", ["size", "1.27", "1.27"]]]],
        ["property", _quoted("Value"), _quoted(f"TP_{net_name}"),
         ["at", str(x + 1.27), str(y + 1.27), "0"],
         ["effects", ["font", ["size", "1.27", "1.27"]]]],
        ["pin", QuotedStr("1"), ["uuid", str(_uuid.uuid4())]],
    ]
    symbol_node[-1:-1] = _make_probe_fields(x, y, role, required, current_ma, side)
    label_uid = str(_uuid.uuid4())
    label_node = [
        "label", _quoted(net_name),
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


def add_protected_testpoint_symbol(
    sch: Schematic,
    net_name: str,
    x: float,
    y: float,
    protection: ProtectionComponent,
    *,
    tp_ref: str = "TP?",
    prot_ref: str = "R?",
    role: str = "",
    required: bool = False,
    current_ma: float = 0.0,
    side: str = "top",
) -> None:
    """Place protection component in series between net and testpoint.

    Layout (vertical, top-to-bottom):
      net_label(net_name) @ (x, y+10.16)
      wire down to resistor pin 1
      resistor/ferrite @ (x, y+5.08)
      wire down to testpoint
      testpoint @ (x, y)
      label(PROBE_net_name) connects to testpoint
    """
    if protection.protection_type == ProtectionType.SERIES_RESISTOR:
        _ensure_resistor_lib_symbol(sch)
        lib_id = "Device:R"
    else:
        _ensure_ferrite_lib_symbol(sch)
        lib_id = "Device:FerriteBead"

    _ensure_lib_symbol(sch)

    probe_net = f"PROBE_{net_name}"

    # Protection component at (x, y+5.08) — pin1 up (original net), pin2 down (probe net)
    prot_x, prot_y = x, y + 5.08
    prot_uid = str(_uuid.uuid4())
    prot_node = [
        "symbol",
        ["lib_id", _quoted(lib_id)],
        ["at", str(prot_x), str(prot_y), "0"],
        ["unit", "1"],
        ["exclude_from_sim", "no"],
        ["in_bom", "yes"],
        ["on_board", "yes"],
        ["dnp", "no"],
        ["uuid", prot_uid],
        ["property", _quoted("Reference"), _quoted(prot_ref),
         ["at", str(prot_x + 1.27), str(prot_y), "0"],
         ["effects", ["font", ["size", "1.27", "1.27"]]]],
        ["property", _quoted("Value"), _quoted(protection.value),
         ["at", str(prot_x + 1.27), str(prot_y + 1.27), "0"],
         ["effects", ["font", ["size", "1.27", "1.27"]]]],
        ["pin", QuotedStr("1"), ["uuid", str(_uuid.uuid4())]],
        ["pin", QuotedStr("2"), ["uuid", str(_uuid.uuid4())]],
    ]
    sch.raw.append(prot_node)

    # Testpoint at (x, y)
    tp_uid = str(_uuid.uuid4())
    tp_node = [
        "symbol",
        ["lib_id", _quoted("Connector:TestPoint")],
        ["at", str(x), str(y), "0"],
        ["unit", "1"],
        ["exclude_from_sim", "no"],
        ["in_bom", "yes"],
        ["on_board", "yes"],
        ["dnp", "no"],
        ["uuid", tp_uid],
        ["property", _quoted("Reference"), _quoted(tp_ref),
         ["at", str(x + 1.27), str(y - 1.27), "0"],
         ["effects", ["font", ["size", "1.27", "1.27"]]]],
        ["property", _quoted("Value"), _quoted(f"TP_{net_name}"),
         ["at", str(x + 1.27), str(y + 1.27), "0"],
         ["effects", ["font", ["size", "1.27", "1.27"]]]],
    ]
    tp_node.extend(_make_probe_fields(x, y, role, required, current_ma, side))
    tp_node.append(["pin", QuotedStr("1"), ["uuid", str(_uuid.uuid4())]])
    sch.raw.append(tp_node)

    # Wire: net label down to protection pin 1
    pin1_y = prot_y + 3.81
    label_y = pin1_y + 2.54
    sch.raw.append([
        "wire",
        ["pts", ["xy", str(x), str(label_y)], ["xy", str(x), str(pin1_y)]],
        ["stroke", ["width", "0"], ["type", "default"]],
        ["uuid", str(_uuid.uuid4())],
    ])

    # Net label for original net (connects to protection pin 1)
    sch.raw.append([
        "label", _quoted(net_name),
        ["at", str(x), str(label_y), "0"],
        ["effects", ["font", ["size", "1.27", "1.27"]]],
        ["uuid", str(_uuid.uuid4())],
    ])

    # Wire: protection pin 2 down to testpoint
    pin2_y = prot_y - 3.81
    sch.raw.append([
        "wire",
        ["pts", ["xy", str(x), str(pin2_y)], ["xy", str(x), str(y)]],
        ["stroke", ["width", "0"], ["type", "default"]],
        ["uuid", str(_uuid.uuid4())],
    ])

    # Probe net label at testpoint (the protected side)
    sch.raw.append([
        "label", _quoted(probe_net),
        ["at", str(x), str(y - 2.54), "0"],
        ["effects", ["font", ["size", "1.27", "1.27"]]],
        ["uuid", str(_uuid.uuid4())],
    ])
    sch.raw.append([
        "wire",
        ["pts", ["xy", str(x), str(y)], ["xy", str(x), str(y - 2.54)]],
        ["stroke", ["width", "0"], ["type", "default"]],
        ["uuid", str(_uuid.uuid4())],
    ])


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
        ["lib_id", _quoted(lib_id)],
        ["at", str(x), str(y), "0"],
        ["unit", "1"],
        ["exclude_from_sim", "no"],
        ["in_bom", "yes"],
        ["on_board", "yes"],
        ["dnp", "no"],
        ["uuid", uid],
        ["property", _quoted("Reference"), _quoted(ref),
         ["at", str(x + 1.27), str(y - 1.27), "0"],
         ["effects", ["font", ["size", "1.27", "1.27"]]]],
        ["property", _quoted("Value"), _quoted(f"CONN_{ref}"),
         ["at", str(x + 1.27), str(y + 1.27), "0"],
         ["effects", ["font", ["size", "1.27", "1.27"]]]],
    ]

    # Add pin entries for each assigned net
    for a in assignments:
        pin_uid = str(_uuid.uuid4())
        symbol_node.append(
            ["pin", QuotedStr(str(a.pin_index + 1)), ["uuid", pin_uid]]
        )

    sch.raw.append(symbol_node)

    # Add global labels for each assigned net (so wires can connect)
    for i, a in enumerate(assignments):
        label_y = y + i * 2.54
        label_node = [
            "global_label", _quoted(a.net_name),
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


def _ensure_resistor_lib_symbol(sch: Schematic) -> None:
    _ensure_generic_lib_symbol(sch, "Device:R", _RESISTOR_LIB_SYMBOL)


def _ensure_ferrite_lib_symbol(sch: Schematic) -> None:
    _ensure_generic_lib_symbol(sch, "Device:FerriteBead", _FERRITE_LIB_SYMBOL)


def _ensure_generic_lib_symbol(
    sch: Schematic, lib_id: str, template: list,
) -> None:
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
            node.append(template)
            return
    sch.raw.append(["lib_symbols", template])


def add_module_sheet_symbol(
    sch: Schematic,
    instance: ModuleInstance,
    sheet_file: str,
    x: float,
    y: float,
    *,
    width: float = 35.56,
    height: float = 20.32,
    run_id: str = "",
) -> None:
    """Add a generated hierarchical sheet symbol for a module instance."""
    uid = str(_uuid.uuid4())
    sheet_node = [
        "sheet",
        ["at", str(x), str(y)],
        ["size", str(width), str(height)],
        ["fields_autoplaced"],
        ["stroke", ["width", "0.1524"], ["type", "solid"]],
        ["fill", ["color", "0", "0", "0", "0.0000"]],
        ["uuid", uid],
        ["property", _quoted("Sheetname"), _quoted(f"{instance.instance_id}_{instance.name}"),
         ["at", str(x), str(y - 1.27), "0"],
         ["effects", ["font", ["size", "1.27", "1.27"]]]],
        ["property", _quoted("Sheetfile"), _quoted(sheet_file),
         ["at", str(x), str(y + height + 1.27), "0"],
         ["effects", ["font", ["size", "1.27", "1.27"]]]],
        ["property", _quoted("APR_MODULE"), _quoted(instance.instance_id),
         ["at", str(x), str(y + height + 3.81), "0"],
         ["effects", ["font", ["size", "1.0", "1.0"]]], "hide"],
        ["property", _quoted("APR_INSTANCE"), _quoted(instance.name),
         ["at", str(x), str(y + height + 5.08), "0"],
         ["effects", ["font", ["size", "1.0", "1.0"]]], "hide"],
        ["property", _quoted("APR_GENERATED"), _quoted("yes"),
         ["at", str(x), str(y + height + 6.35), "0"],
         ["effects", ["font", ["size", "1.0", "1.0"]]], "hide"],
    ]
    if run_id:
        sheet_node.append([
            "property", _quoted("APR_RUN_ID"), _quoted(run_id),
            ["at", str(x), str(y + height + 7.62), "0"],
            ["effects", ["font", ["size", "1.0", "1.0"]]], "hide",
        ])
    for index, net_name in enumerate(_sheet_pins(instance)):
        pin_y = y + 3.81 + index * 2.54
        if pin_y > y + height - 2.54:
            break
        sheet_node.append([
            "pin", QuotedStr(net_name), "input",
            ["at", "0", str(round(pin_y - y, 3)), "180"],
            ["effects", ["font", ["size", "1.0", "1.0"]]],
            ["uuid", str(_uuid.uuid4())],
        ])
    sch.raw.append(sheet_node)


def _sheet_pins(instance: ModuleInstance) -> list[str]:
    pins = []
    pins.extend(instance.target_nets)
    pins.extend(instance.generated_nets)
    pins.extend(instance.rails)
    pins.extend(instance.voltage_domains)
    deduped: list[str] = []
    for pin in pins:
        if pin and pin not in deduped:
            deduped.append(pin)
    return deduped


def write_schematic(sch: Schematic, path: str | Path) -> None:
    repair_schematic_tree(sch.raw)
    text = serialize(sch.raw) + "\n"
    Path(path).write_text(text, encoding="utf-8")
