#!/usr/bin/env python3
"""Generate KiCad schematic and PCB for ESP32-S3 Bluetooth audio pickup board."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ai_probe_router.eda_adapters.kicad.sexpr import QuotedStr, serialize
from ai_probe_router.models.board import Board, Schematic


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Schematic
# ---------------------------------------------------------------------------

def build_schematic() -> Schematic:
    raw: list = [
        "kicad_sch",
        ["version", "20231120"],
        ["generator", "eeschema"],
        ["generator_version", "8.0"],
        ["uuid", _uuid()],
        ["paper", "A4"],
        lib_symbols(),
        *symbols(),
        *wires(),
        *labels(),
    ]
    return Schematic(components=[], labels=[], wires=[], raw=raw)


def lib_symbols() -> list:
    """All library symbol definitions used in this schematic."""
    return [
        "lib_symbols",
        # ESP32-S3-WROOM-1 (simplified — only used pins)
        ["symbol", "MCU_Espressif:ESP32-S3-WROOM-1",
         ["in_bom", "yes"],
         ["on_board", "yes"],
         ["property", "Reference", "U",
          ["at", "-10.16", "15.24", "0"],
          ["effects", ["font", ["size", "1.27", "1.27"]]]],
         ["property", "Value", "ESP32-S3-WROOM-1-N8",
          ["at", "0", "0", "0"],
          ["effects", ["font", ["size", "1.27", "1.27"]]]],
         ["symbol", "ESP32-S3-WROOM-1_0_1",
          ["rectangle",
           ["start", "-12.7", "17.78"],
           ["end", "12.7", "-17.78"],
           ["stroke", ["width", "0.254"], ["type", "default"]],
           ["fill", ["type", "background"]]]],
         ["symbol", "ESP32-S3-WROOM-1_1_1",
          ["pin", "passive", "line", ["at", "-15.24", "13.97", "0"], ["length", "2.54"],
           ["name", "GPIO1", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "1", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "passive", "line", ["at", "-15.24", "11.43", "0"], ["length", "2.54"],
           ["name", "GPIO2", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "2", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "passive", "line", ["at", "-15.24", "8.89", "0"], ["length", "2.54"],
           ["name", "GPIO4", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "4", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "passive", "line", ["at", "-15.24", "6.35", "0"], ["length", "2.54"],
           ["name", "GPIO5", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "5", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "passive", "line", ["at", "-15.24", "3.81", "0"], ["length", "2.54"],
           ["name", "GPIO6", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "6", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "passive", "line", ["at", "-15.24", "1.27", "0"], ["length", "2.54"],
           ["name", "GPIO7", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "7", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "passive", "line", ["at", "-15.24", "-1.27", "0"], ["length", "2.54"],
           ["name", "GPIO19", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "19", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "passive", "line", ["at", "-15.24", "-3.81", "0"], ["length", "2.54"],
           ["name", "GPIO20", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "20", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "passive", "line", ["at", "15.24", "13.97", "180"], ["length", "2.54"],
           ["name", "GPIO0", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "0", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "passive", "line", ["at", "15.24", "11.43", "180"], ["length", "2.54"],
           ["name", "GPIO3", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "3", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "passive", "line", ["at", "15.24", "8.89", "180"], ["length", "2.54"],
           ["name", "GPIO45", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "45", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "passive", "line", ["at", "15.24", "6.35", "180"], ["length", "2.54"],
           ["name", "GPIO46", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "46", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "power_in", "line", ["at", "0", "-20.32", "90"], ["length", "2.54"],
           ["name", "GND", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "GND", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "power_in", "line", ["at", "0", "20.32", "270"], ["length", "2.54"],
           ["name", "3V3", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "3V3", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "power_in", "line", ["at", "0", "17.78", "270"], ["length", "2.54"],
           ["name", "VBAT", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "VBAT", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
         ],
        ],
        # TP4056
        ["symbol", "Battery_Management:TP4056",
         ["in_bom", "yes"],
         ["on_board", "yes"],
         ["property", "Reference", "U",
          ["at", "-5.08", "6.35", "0"],
          ["effects", ["font", ["size", "1.27", "1.27"]]]],
         ["property", "Value", "TP4056",
          ["at", "0", "0", "0"],
          ["effects", ["font", ["size", "1.27", "1.27"]]]],
         ["symbol", "TP4056_0_1",
          ["rectangle",
           ["start", "-6.35", "5.08"],
           ["end", "6.35", "-5.08"],
           ["stroke", ["width", "0.254"], ["type", "default"]],
           ["fill", ["type", "background"]]]],
         ["symbol", "TP4056_1_1",
          ["pin", "power_in", "line", ["at", "-8.89", "2.54", "0"], ["length", "2.54"],
           ["name", "VCC", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "1", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "power_out", "line", ["at", "8.89", "2.54", "180"], ["length", "2.54"],
           ["name", "BAT", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "2", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "power_in", "line", ["at", "0", "-7.62", "90"], ["length", "2.54"],
           ["name", "GND", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "3", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
         ],
        ],
        # XC6206 LDO
        ["symbol", "Regulator_Linear:XC6206P332MR",
         ["in_bom", "yes"],
         ["on_board", "yes"],
         ["property", "Reference", "U",
          ["at", "-3.81", "3.81", "0"],
          ["effects", ["font", ["size", "1.27", "1.27"]]]],
         ["property", "Value", "XC6206P332MR",
          ["at", "0", "0", "0"],
          ["effects", ["font", ["size", "1.27", "1.27"]]]],
         ["symbol", "XC6206P332MR_0_1",
          ["rectangle",
           ["start", "-5.08", "2.54"],
           ["end", "5.08", "-2.54"],
           ["stroke", ["width", "0.254"], ["type", "default"]],
           ["fill", ["type", "background"]]]],
         ["symbol", "XC6206P332MR_1_1",
          ["pin", "power_in", "line", ["at", "-7.62", "0", "0"], ["length", "2.54"],
           ["name", "VI", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "1", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "power_out", "line", ["at", "7.62", "0", "180"], ["length", "2.54"],
           ["name", "VO", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "2", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "power_in", "line", ["at", "0", "-5.08", "90"], ["length", "2.54"],
           ["name", "GND", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", "3", ["effects", ["font", ["size", "1.27", "1.27"]]]]],
         ],
        ],
        # Resistor
        ["symbol", "Device:R",
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
           ["at", "0", "3.81", "270"], ["length", "1.27"],
           ["name", "~", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", QuotedStr("1"), ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "passive", "line",
           ["at", "0", "-3.81", "90"], ["length", "1.27"],
           ["name", "~", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", QuotedStr("2"), ["effects", ["font", ["size", "1.27", "1.27"]]]]],
         ],
        ],
        # Capacitor
        ["symbol", "Device:C",
         ["pin_names", ["offset", "0.254"]],
         ["in_bom", "yes"],
         ["on_board", "yes"],
         ["symbol", "C_0_1",
          ["polyline",
           ["pts", ["xy", "-2.032", "-0.762"], ["xy", "2.032", "-0.762"]],
           ["stroke", ["width", "0.254"], ["type", "default"]],
           ["fill", ["type", "none"]]],
          ["polyline",
           ["pts", ["xy", "-2.032", "0.762"], ["xy", "2.032", "0.762"]],
           ["stroke", ["width", "0.254"], ["type", "default"]],
           ["fill", ["type", "none"]]]],
         ["symbol", "C_1_1",
          ["pin", "passive", "line",
           ["at", "0", "-2.54", "90"], ["length", "1.27"],
           ["name", "~", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", QuotedStr("1"), ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "passive", "line",
           ["at", "0", "2.54", "270"], ["length", "1.27"],
           ["name", "~", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", QuotedStr("2"), ["effects", ["font", ["size", "1.27", "1.27"]]]]],
         ],
        ],
        # LED
        ["symbol", "Device:LED",
         ["pin_numbers", "hide"],
         ["in_bom", "yes"],
         ["on_board", "yes"],
         ["symbol", "LED_0_1",
          ["polyline",
           ["pts", ["xy", "-1.27", "-1.27"], ["xy", "0", "0"], ["xy", "1.27", "-1.27"]],
           ["stroke", ["width", "0.2032"], ["type", "default"]],
           ["fill", ["type", "none"]]],
          ["polyline",
           ["pts", ["xy", "-1.27", "1.27"], ["xy", "0", "0"], ["xy", "1.27", "1.27"]],
           ["stroke", ["width", "0.2032"], ["type", "default"]],
           ["fill", ["type", "none"]]],
          ["polyline",
           ["pts", ["xy", "1.27", "1.27"], ["xy", "1.27", "0.508"], ["xy", "0.762", "0.762"]],
           ["stroke", ["width", "0.2032"], ["type", "default"]],
           ["fill", ["type", "none"]]],
          ["polyline",
           ["pts", ["xy", "1.27", "1.27"], ["xy", "1.27", "0"], ["xy", "0.508", "0.635"]],
           ["stroke", ["width", "0.2032"], ["type", "default"]],
           ["fill", ["type", "none"]]]],
         ["symbol", "LED_1_1",
          ["pin", "passive", "line",
           ["at", "0", "-2.54", "90"], ["length", "2.54"],
           ["name", "K", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", QuotedStr("1"), ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "passive", "line",
           ["at", "0", "2.54", "270"], ["length", "2.54"],
           ["name", "A", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", QuotedStr("2"), ["effects", ["font", ["size", "1.27", "1.27"]]]]],
         ],
        ],
        # Switch (push button)
        ["symbol", "Switch:SW_Push",
         ["in_bom", "yes"],
         ["on_board", "yes"],
         ["symbol", "SW_Push_0_1",
          ["circle", ["center", "-2.032", "0"], ["radius", "0.508"],
           ["stroke", ["width", "0"], ["type", "default"]],
           ["fill", ["type", "none"]]],
          ["circle", ["center", "2.032", "0"], ["radius", "0.508"],
           ["stroke", ["width", "0"], ["type", "default"]],
           ["fill", ["type", "none"]]],
          ["polyline",
           ["pts", ["xy", "-2.032", "0"], ["xy", "-0.508", "0"], ["xy", "0.508", "1.27"], ["xy", "2.032", "1.27"]],
           ["stroke", ["width", "0.254"], ["type", "default"]],
           ["fill", ["type", "none"]]]],
         ["symbol", "SW_Push_1_1",
          ["pin", "passive", "line",
           ["at", "-5.08", "0", "0"], ["length", "2.54"],
           ["name", "1", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", QuotedStr("1"), ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "passive", "line",
           ["at", "5.08", "0", "180"], ["length", "2.54"],
           ["name", "2", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", QuotedStr("2"), ["effects", ["font", ["size", "1.27", "1.27"]]]]],
         ],
        ],
        # Microphone (simplified electret)
        ["symbol", "Audio:Microphone",
         ["in_bom", "yes"],
         ["on_board", "yes"],
         ["symbol", "Microphone_0_1",
          ["circle", ["center", "0", "0"], ["radius", "2.54"],
           ["stroke", ["width", "0.254"], ["type", "default"]],
           ["fill", ["type", "none"]]],
          ["polyline",
           ["pts", ["xy", "-1.27", "-1.27"], ["xy", "-1.27", "1.27"]],
           ["stroke", ["width", "0.254"], ["type", "default"]],
           ["fill", ["type", "none"]]],
          ["polyline",
           ["pts", ["xy", "-1.27", "0"], ["xy", "-2.54", "0"]],
           ["stroke", ["width", "0.254"], ["type", "default"]],
           ["fill", ["type", "none"]]],
         ],
         ["symbol", "Microphone_1_1",
          ["pin", "passive", "line",
           ["at", "-5.08", "0", "0"], ["length", "2.54"],
           ["name", "+", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", QuotedStr("1"), ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "passive", "line",
           ["at", "0", "-5.08", "90"], ["length", "2.54"],
           ["name", "-", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", QuotedStr("2"), ["effects", ["font", ["size", "1.27", "1.27"]]]]],
         ],
        ],
        # Battery connector
        ["symbol", "Connector:Battery_Cell",
         ["in_bom", "yes"],
         ["on_board", "yes"],
         ["symbol", "Battery_Cell_0_1",
          ["rectangle",
           ["start", "-2.032", "-1.016"],
           ["end", "2.032", "1.016"],
           ["stroke", ["width", "0.254"], ["type", "default"]],
           ["fill", ["type", "outline"]]],
          ["polyline",
           ["pts", ["xy", "-1.27", "2.54"], ["xy", "1.27", "2.54"]],
           ["stroke", ["width", "0.254"], ["type", "default"]],
           ["fill", ["type", "none"]]]],
         ["symbol", "Battery_Cell_1_1",
          ["pin", "passive", "line",
           ["at", "0", "-3.81", "90"], ["length", "2.54"],
           ["name", "+", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", QuotedStr("1"), ["effects", ["font", ["size", "1.27", "1.27"]]]]],
          ["pin", "passive", "line",
           ["at", "0", "3.81", "270"], ["length", "2.54"],
           ["name", "-", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", QuotedStr("2"), ["effects", ["font", ["size", "1.27", "1.27"]]]]],
         ],
        ],
        # Power symbols
        ["symbol", "power:GND",
         ["power"],
         ["pin_numbers", "hide"],
         ["in_bom", "yes"],
         ["on_board", "yes"],
         ["property", "Reference", "#PWR",
          ["at", "0", "-3.81", "0"],
          ["effects", ["font", ["size", "1.27", "1.27"]], "hide"]],
         ["property", "Value", "GND",
          ["at", "0", "-1.27", "0"],
          ["effects", ["font", ["size", "1.27", "1.27"]]]],
         ["symbol", "GND_0_1",
          ["polyline",
           ["pts", ["xy", "0", "0"], ["xy", "0", "-1.27"], ["xy", "1.27", "-1.27"],
            ["xy", "0", "-2.54"], ["xy", "-1.27", "-1.27"], ["xy", "0", "-1.27"]],
           ["stroke", ["width", "0"], ["type", "default"]],
           ["fill", ["type", "none"]]]],
         ["symbol", "GND_1_1",
          ["pin", "power_in", "line", ["at", "0", "0", "270"], ["length", "0"],
           ["name", "GND", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", QuotedStr("1"), ["effects", ["font", ["size", "1.27", "1.27"]]]]],
         ],
        ],
        ["symbol", "power:+3.3V",
         ["power"],
         ["pin_numbers", "hide"],
         ["in_bom", "yes"],
         ["on_board", "yes"],
         ["property", "Reference", "#PWR",
          ["at", "0", "-3.81", "0"],
          ["effects", ["font", ["size", "1.27", "1.27"]], "hide"]],
         ["property", "Value", "+3.3V",
          ["at", "0", "1.27", "0"],
          ["effects", ["font", ["size", "1.27", "1.27"]]]],
         ["symbol", "+3.3V_0_1",
          ["polyline",
           ["pts", ["xy", "-0.762", "1.27"], ["xy", "0", "2.54"]],
           ["stroke", ["width", "0"], ["type", "default"]],
           ["fill", ["type", "none"]]],
          ["polyline",
           ["pts", ["xy", "0", "0"], ["xy", "0", "2.54"]],
           ["stroke", ["width", "0"], ["type", "default"]],
           ["fill", ["type", "none"]]],
          ["polyline",
           ["pts", ["xy", "0", "2.54"], ["xy", "0.762", "1.27"]],
           ["stroke", ["width", "0"], ["type", "default"]],
           ["fill", ["type", "none"]]]],
         ["symbol", "+3.3V_1_1",
          ["pin", "power_in", "line", ["at", "0", "0", "90"], ["length", "0"],
           ["name", "+3.3V", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", QuotedStr("1"), ["effects", ["font", ["size", "1.27", "1.27"]]]]],
         ],
        ],
        ["symbol", "power:VBAT",
         ["power"],
         ["pin_numbers", "hide"],
         ["in_bom", "yes"],
         ["on_board", "yes"],
         ["property", "Reference", "#PWR",
          ["at", "0", "-3.81", "0"],
          ["effects", ["font", ["size", "1.27", "1.27"]], "hide"]],
         ["property", "Value", "VBAT",
          ["at", "0", "1.27", "0"],
          ["effects", ["font", ["size", "1.27", "1.27"]]]],
         ["symbol", "VBAT_0_1",
          ["polyline",
           ["pts", ["xy", "-0.762", "1.27"], ["xy", "0", "2.54"]],
           ["stroke", ["width", "0"], ["type", "default"]],
           ["fill", ["type", "none"]]],
          ["polyline",
           ["pts", ["xy", "0", "0"], ["xy", "0", "2.54"]],
           ["stroke", ["width", "0"], ["type", "default"]],
           ["fill", ["type", "none"]]],
          ["polyline",
           ["pts", ["xy", "0", "2.54"], ["xy", "0.762", "1.27"]],
           ["stroke", ["width", "0"], ["type", "default"]],
           ["fill", ["type", "none"]]]],
         ["symbol", "VBAT_1_1",
          ["pin", "power_in", "line", ["at", "0", "0", "90"], ["length", "0"],
           ["name", "VBAT", ["effects", ["font", ["size", "1.27", "1.27"]]]],
           ["number", QuotedStr("1"), ["effects", ["font", ["size", "1.27", "1.27"]]]]],
         ],
        ],
    ]


def _sym(lib_id: str, ref: str, value: str, x: float, y: float, rotation: float = 0.0, pins: dict[str, str] | None = None) -> list:
    """Build a symbol instance node."""
    node = [
        "symbol",
        ["lib_id", lib_id],
        ["at", str(x), str(y), str(rotation)],
        ["unit", "1"],
        ["exclude_from_sim", "no"],
        ["in_bom", "yes"],
        ["on_board", "yes"],
        ["dnp", "no"],
        ["uuid", _uuid()],
        ["property", "Reference", ref,
         ["at", str(x - 1.27), str(y + 2.54), "0"],
         ["effects", ["font", ["size", "1.27", "1.27"]], ["justify", "left"]]],
        ["property", "Value", value,
         ["at", str(x - 1.27), str(y - 2.54), "0"],
         ["effects", ["font", ["size", "1.27", "1.27"]], ["justify", "left"]]],
    ]
    if pins:
        for num, uid_val in pins.items():
            node.append(["pin", QuotedStr(num), ["uuid", uid_val]])
    return node


def symbols() -> list[list]:
    """All placed symbol instances."""
    syms = []

    # U1: ESP32-S3-WROOM-1 at (100, 100)
    u1_pins = {str(i): _uuid() for i in ["1", "2", "4", "5", "6", "7", "19", "20", "0", "3", "45", "46", "GND", "3V3", "VBAT"]}
    syms.append(_sym("MCU_Espressif:ESP32-S3-WROOM-1", "U1", "ESP32-S3-WROOM-1-N8", 100.0, 100.0, 0.0, u1_pins))

    # U2: TP4056 at (50, 100)
    u2_pins = {"1": _uuid(), "2": _uuid(), "3": _uuid()}
    syms.append(_sym("Battery_Management:TP4056", "U2", "TP4056", 50.0, 100.0, 0.0, u2_pins))

    # U3: XC6206 LDO at (50, 130)
    u3_pins = {"1": _uuid(), "2": _uuid(), "3": _uuid()}
    syms.append(_sym("Regulator_Linear:XC6206P332MR", "U3", "XC6206P332MR", 50.0, 130.0, 0.0, u3_pins))

    # R1: 10k pull-up for KEY_VOL_UP at (140, 110)
    syms.append(_sym("Device:R", "R1", "10k", 140.0, 110.0, 0.0, {"1": _uuid(), "2": _uuid()}))

    # R2: 10k pull-up for KEY_VOL_DOWN at (140, 100)
    syms.append(_sym("Device:R", "R2", "10k", 140.0, 100.0, 0.0, {"1": _uuid(), "2": _uuid()}))

    # R3: 1k LED_PWR current limit at (140, 90)
    syms.append(_sym("Device:R", "R3", "1k", 140.0, 90.0, 0.0, {"1": _uuid(), "2": _uuid()}))

    # R4: 1k LED_BT current limit at (140, 80)
    syms.append(_sym("Device:R", "R4", "1k", 140.0, 80.0, 0.0, {"1": _uuid(), "2": _uuid()}))

    # R5: 100k battery divider upper at (50, 70)
    syms.append(_sym("Device:R", "R5", "100k", 50.0, 70.0, 0.0, {"1": _uuid(), "2": _uuid()}))

    # R6: 100k battery divider lower at (50, 55)
    syms.append(_sym("Device:R", "R6", "100k", 50.0, 55.0, 0.0, {"1": _uuid(), "2": _uuid()}))

    # R7: 2.2k mic bias at (150, 120)
    syms.append(_sym("Device:R", "R7", "2.2k", 150.0, 120.0, 0.0, {"1": _uuid(), "2": _uuid()}))

    # C1: 10uF bulk cap near U1 at (80, 130)
    syms.append(_sym("Device:C", "C1", "10uF", 80.0, 130.0, 0.0, {"1": _uuid(), "2": _uuid()}))

    # C2: 100nF decoupling U1 at (80, 140)
    syms.append(_sym("Device:C", "C2", "100nF", 80.0, 140.0, 0.0, {"1": _uuid(), "2": _uuid()}))

    # C3: 100nF decoupling U3 at (65, 130)
    syms.append(_sym("Device:C", "C3", "100nF", 65.0, 130.0, 0.0, {"1": _uuid(), "2": _uuid()}))

    # C4: 1uF LDO output at (35, 130)
    syms.append(_sym("Device:C", "C4", "1uF", 35.0, 130.0, 0.0, {"1": _uuid(), "2": _uuid()}))

    # C5: 10uF mic coupling at (165, 120)
    syms.append(_sym("Device:C", "C5", "10uF", 165.0, 120.0, 0.0, {"1": _uuid(), "2": _uuid()}))

    # D1: LED_PWR (red)
    syms.append(_sym("Device:LED", "D1", "LED_RED", 140.0, 70.0, 0.0, {"1": _uuid(), "2": _uuid()}))

    # D2: LED_BT (blue)
    syms.append(_sym("Device:LED", "D2", "LED_BLUE", 140.0, 60.0, 0.0, {"1": _uuid(), "2": _uuid()}))

    # SW1: KEY_VOL_UP at (160, 110)
    syms.append(_sym("Switch:SW_Push", "SW1", "KEY_VOL_UP", 160.0, 110.0, 0.0, {"1": _uuid(), "2": _uuid()}))

    # SW2: KEY_VOL_DOWN at (160, 100)
    syms.append(_sym("Switch:SW_Push", "SW2", "KEY_VOL_DOWN", 160.0, 100.0, 0.0, {"1": _uuid(), "2": _uuid()}))

    # MK1: Microphone at (170, 120)
    syms.append(_sym("Audio:Microphone", "MK1", "MIC_ELECTRET", 170.0, 120.0, 0.0, {"1": _uuid(), "2": _uuid()}))

    # BT1: Battery
    syms.append(_sym("Connector:Battery_Cell", "BT1", "LiPo_3V7", 20.0, 100.0, 0.0, {"1": _uuid(), "2": _uuid()}))

    # Power symbols
    syms.append(_sym("power:GND", "#PWR01", "GND", 100.0, 125.0, 0.0, {"1": _uuid()}))
    syms.append(_sym("power:+3.3V", "#PWR02", "+3.3V", 100.0, 75.0, 0.0, {"1": _uuid()}))
    syms.append(_sym("power:VBAT", "#PWR03", "VBAT", 50.0, 150.0, 0.0, {"1": _uuid()}))
    syms.append(_sym("power:GND", "#PWR04", "GND", 50.0, 85.0, 0.0, {"1": _uuid()}))
    syms.append(_sym("power:GND", "#PWR05", "GND", 140.0, 50.0, 0.0, {"1": _uuid()}))
    syms.append(_sym("power:GND", "#PWR06", "GND", 50.0, 40.0, 0.0, {"1": _uuid()}))
    syms.append(_sym("power:GND", "#PWR07", "GND", 170.0, 110.0, 0.0, {"1": _uuid()}))
    syms.append(_sym("power:GND", "#PWR08", "GND", 80.0, 150.0, 0.0, {"1": _uuid()}))

    return syms


def _wire(x1: float, y1: float, x2: float, y2: float) -> list:
    return [
        "wire",
        ["pts", ["xy", str(x1), str(y1)], ["xy", str(x2), str(y2)]],
        ["stroke", ["width", "0"], ["type", "default"]],
        ["uuid", _uuid()],
    ]


def _global_label(name: str, x: float, y: float, angle: float) -> list:
    justify = "left" if angle in (0, 180) else "left"
    return [
        "global_label", name,
        ["shape", "input"],
        ["at", str(x), str(y), str(angle)],
        ["effects", ["font", ["size", "1.27", "1.27"]], ["justify", justify]],
        ["uuid", _uuid()],
    ]


def wires() -> list[list]:
    """Wire segments connecting components."""
    w = []
    # U1 power
    w.append(_wire(100.0, 117.78, 100.0, 125.0))   # GND down to GND symbol
    w.append(_wire(100.0, 82.22, 100.0, 75.0))     # 3V3 up to 3V3 symbol
    w.append(_wire(100.0, 82.22, 90.0, 82.22))     # 3V3 horizontal stub

    # U1 signal pins to labels
    w.append(_wire(84.76, 113.97, 80.0, 113.97))   # GPIO1 -> label
    w.append(_wire(84.76, 111.43, 80.0, 111.43))   # GPIO2 -> label
    w.append(_wire(84.76, 108.89, 80.0, 108.89))   # GPIO4 -> label
    w.append(_wire(84.76, 106.35, 80.0, 106.35))   # GPIO5 -> label
    w.append(_wire(84.76, 103.81, 80.0, 103.81))   # GPIO6 -> label
    w.append(_wire(84.76, 101.27, 80.0, 101.27))   # GPIO7 -> label
    w.append(_wire(84.76, 98.73, 80.0, 98.73))     # GPIO19 -> label
    w.append(_wire(84.76, 96.19, 80.0, 96.19))     # GPIO20 -> label

    w.append(_wire(115.24, 113.97, 120.0, 113.97)) # GPIO0 -> label
    w.append(_wire(115.24, 111.43, 120.0, 111.43)) # GPIO3 -> label
    w.append(_wire(115.24, 108.89, 120.0, 108.89)) # GPIO45 -> label
    w.append(_wire(115.24, 106.35, 120.0, 106.35)) # GPIO46 -> label

    # U2 TP4056
    w.append(_wire(41.11, 102.54, 35.0, 102.54))   # VCC left to VBUS label
    w.append(_wire(58.89, 102.54, 65.0, 102.54))   # BAT right to VBAT label
    w.append(_wire(50.0, 94.92, 50.0, 90.0))       # GND down

    # U3 LDO
    w.append(_wire(42.38, 130.0, 35.0, 130.0))     # VI left to VBAT
    w.append(_wire(57.62, 130.0, 65.0, 130.0))     # VO right to 3V3
    w.append(_wire(50.0, 127.46, 50.0, 122.0))     # GND down

    # Battery divider (R5/R6)
    w.append(_wire(50.0, 65.0, 50.0, 60.0))        # R5 bottom to R6 top
    w.append(_wire(50.0, 50.0, 50.0, 48.0))        # R6 bottom to GND
    w.append(_wire(55.0, 57.5, 65.0, 57.5))        # divider tap to VBATT_DIV label

    # LEDs and resistors
    w.append(_wire(140.0, 86.27, 140.0, 82.5))     # R3 bottom to D1 anode
    w.append(_wire(140.0, 72.46, 140.0, 70.0))     # D1 cathode to GND symbol
    w.append(_wire(140.0, 76.27, 140.0, 72.5))     # R4 bottom to D2 anode
    w.append(_wire(140.0, 62.46, 140.0, 60.0))     # D2 cathode to GND symbol

    # Keys and pull-ups
    w.append(_wire(140.0, 113.73, 140.0, 112.0))   # R1 bottom to SW1 top
    w.append(_wire(160.0, 110.0, 160.0, 108.0))    # SW1 bottom to GND
    w.append(_wire(140.0, 103.73, 140.0, 102.0))   # R2 bottom to SW2 top
    w.append(_wire(160.0, 100.0, 160.0, 98.0))     # SW2 bottom to GND

    # Mic circuit
    w.append(_wire(150.0, 116.27, 150.0, 114.0))   # R7 bottom to C5 top
    w.append(_wire(165.0, 114.0, 165.0, 112.0))    # C5 bottom to MK1+
    w.append(_wire(170.0, 115.0, 170.0, 114.0))    # MK1- to GND

    # Capacitors to GND
    w.append(_wire(80.0, 133.73, 80.0, 136.0))     # C1 bottom to GND
    w.append(_wire(80.0, 143.73, 80.0, 146.0))     # C2 bottom to GND
    w.append(_wire(65.0, 133.73, 65.0, 136.0))     # C3 bottom to GND
    w.append(_wire(35.0, 133.73, 35.0, 136.0))     # C4 bottom to GND

    # Battery
    w.append(_wire(20.0, 96.19, 20.0, 90.0))       # BAT+ to VBAT net
    w.append(_wire(20.0, 103.81, 20.0, 110.0))     # BAT- to GND

    return w


def labels() -> list[list]:
    """Net labels (global labels for all signals)."""
    lbls = []
    # Left side (MCU outputs / inputs)
    lbls.append(_global_label("ADC_MIC_GPIO1", 80.0, 113.97, 180.0))
    lbls.append(_global_label("KEY_VOL_UP_GPIO2", 80.0, 111.43, 180.0))
    lbls.append(_global_label("KEY_VOL_DOWN_GPIO4", 80.0, 108.89, 180.0))
    lbls.append(_global_label("LED_PWR_GPIO5", 80.0, 106.35, 180.0))
    lbls.append(_global_label("LED_BT_GPIO6", 80.0, 103.81, 180.0))
    lbls.append(_global_label("VBATT_DIV_GPIO7", 80.0, 101.27, 180.0))
    lbls.append(_global_label("USB_DM_GPIO19", 80.0, 98.73, 180.0))
    lbls.append(_global_label("USB_DP_GPIO20", 80.0, 96.19, 180.0))

    # Right side (strapping pins)
    lbls.append(_global_label("BOOT_GPIO0", 120.0, 113.97, 0.0))
    lbls.append(_global_label("GPIO3", 120.0, 111.43, 0.0))
    lbls.append(_global_label("GPIO45", 120.0, 108.89, 0.0))
    lbls.append(_global_label("GPIO46", 120.0, 106.35, 0.0))

    # Power labels
    lbls.append(_global_label("GND", 100.0, 125.0, 270.0))
    lbls.append(_global_label("3V3", 100.0, 75.0, 90.0))
    lbls.append(_global_label("VBAT", 50.0, 150.0, 90.0))
    lbls.append(_global_label("GND", 50.0, 90.0, 270.0))
    lbls.append(_global_label("GND", 140.0, 50.0, 270.0))
    lbls.append(_global_label("GND", 50.0, 48.0, 270.0))
    lbls.append(_global_label("GND", 170.0, 114.0, 270.0))
    lbls.append(_global_label("GND", 80.0, 150.0, 270.0))
    lbls.append(_global_label("VBUS", 35.0, 102.54, 180.0))
    lbls.append(_global_label("VBATT_DIV", 65.0, 57.5, 0.0))

    return lbls


# ---------------------------------------------------------------------------
# PCB
# ---------------------------------------------------------------------------

def build_pcb() -> Board:
    raw: list = [
        "kicad_pcb",
        ["version", "20240108"],
        ["generator", "pcbnew"],
        ["general", ["thickness", "1.6"], ["legacy_teardrops", "no"]],
        ["paper", "A4"],
        ["layers",
         ["0", "F.Cu", "signal"],
         ["31", "B.Cu", "signal"],
         ["36", "B.SilkS", "user", "B.Silkscreen"],
         ["37", "F.SilkS", "user", "F.Silkscreen"],
         ["38", "B.Mask", "user", "B.Mask"],
         ["39", "F.Mask", "user", "F.Mask"],
         ["44", "Edge.Cuts", "user"]],
        ["setup",
         ["pad_to_mask_clearance", "0.05"],
         ["allow_soldermask_bridges_in_footprints", "no"]],
        ["net", "0", ""],
        ["net", "1", "GND"],
        ["net", "2", "3V3"],
        ["net", "3", "VBAT"],
        ["net", "4", "VBUS"],
        ["net", "5", "ADC_MIC_GPIO1"],
        ["net", "6", "KEY_VOL_UP_GPIO2"],
        ["net", "7", "KEY_VOL_DOWN_GPIO4"],
        ["net", "8", "LED_PWR_GPIO5"],
        ["net", "9", "LED_BT_GPIO6"],
        ["net", "10", "VBATT_DIV_GPIO7"],
        ["net", "11", "USB_DM_GPIO19"],
        ["net", "12", "USB_DP_GPIO20"],
        ["net", "13", "BOOT_GPIO0"],
        ["net", "14", "GPIO3"],
        ["net", "15", "GPIO45"],
        ["net", "16", "GPIO46"],
        ["net", "17", "VBATT_DIV"],
        *footprints(),
        board_outline(),
    ]
    return Board(raw=raw)


def _fp(lib_name: str, ref: str, value: str, x: float, y: float, rotation: float = 0.0, pads: list[list] | None = None) -> list:
    fp = [
        "footprint", lib_name,
        ["layer", "F.Cu"],
        ["at", str(x), str(y), str(rotation)],
        ["uuid", _uuid()],
        ["property", "Reference", ref,
         ["at", str(x - 2), str(y + 2), "0"],
         ["layer", "F.SilkS"],
         ["hide", "no"],
         ["effects", ["font", ["size", "1", "1"], ["thickness", "0.15"]]]],
        ["property", "Value", value,
         ["at", str(x - 2), str(y - 2), "0"],
         ["layer", "F.Fab"],
         ["hide", "no"],
         ["effects", ["font", ["size", "1", "1"], ["thickness", "0.15"]]]],
    ]
    if pads:
        for p in pads:
            fp.append(p)
    return fp


def _pad(num: str, pad_type: str, shape: str, x: float, y: float, w: float, h: float, net_id: int, net_name: str, drill: float = 0.0) -> list:
    pad = [
        "pad", QuotedStr(num), pad_type, shape,
        ["at", str(x), str(y)],
        ["size", str(w), str(h)],
    ]
    if drill > 0:
        pad.append(["drill", str(drill)])
    pad.extend([
        ["layers", "F.Cu", "F.Paste", "F.Mask"],
        ["net", str(net_id), net_name],
        ["uuid", _uuid()],
    ])
    return pad


def footprints() -> list[list]:
    fps = []

    # U1: ESP32-S3-WROOM-1 (approx 18×25.5 mm, SMD)
    fps.append(_fp(
        "RF_Module:ESP32-S3-WROOM-1", "U1", "ESP32-S3-WROOM-1-N8",
        30.0, 20.0, 0.0,
        [
            _pad("1", "smd", "rect", -8.0, 10.0, 1.0, 0.8, 5, "ADC_MIC_GPIO1"),
            _pad("2", "smd", "rect", -6.5, 10.0, 1.0, 0.8, 6, "KEY_VOL_UP_GPIO2"),
            _pad("4", "smd", "rect", -3.5, 10.0, 1.0, 0.8, 7, "KEY_VOL_DOWN_GPIO4"),
            _pad("5", "smd", "rect", -2.0, 10.0, 1.0, 0.8, 8, "LED_PWR_GPIO5"),
            _pad("6", "smd", "rect", -0.5, 10.0, 1.0, 0.8, 9, "LED_BT_GPIO6"),
            _pad("7", "smd", "rect", 1.0, 10.0, 1.0, 0.8, 10, "VBATT_DIV_GPIO7"),
            _pad("19", "smd", "rect", 7.0, 10.0, 1.0, 0.8, 11, "USB_DM_GPIO19"),
            _pad("20", "smd", "rect", 8.5, 10.0, 1.0, 0.8, 12, "USB_DP_GPIO20"),
            _pad("0", "smd", "rect", 8.0, -10.0, 1.0, 0.8, 13, "BOOT_GPIO0"),
            _pad("3", "smd", "rect", 6.5, -10.0, 1.0, 0.8, 14, "GPIO3"),
            _pad("45", "smd", "rect", 3.5, -10.0, 1.0, 0.8, 15, "GPIO45"),
            _pad("46", "smd", "rect", 2.0, -10.0, 1.0, 0.8, 16, "GPIO46"),
            _pad("GND", "smd", "rect", 0.0, -10.0, 1.5, 0.8, 1, "GND"),
            _pad("3V3", "smd", "rect", 0.0, 10.0, 1.5, 0.8, 2, "3V3"),
            _pad("VBAT", "smd", "rect", -2.0, 8.0, 1.0, 0.8, 3, "VBAT"),
        ],
    ))

    # U2: TP4056 (SOT-23-5-ish, simplified)
    fps.append(_fp(
        "Package_TO_SOT_SMD:SOT-23-5", "U2", "TP4056",
        10.0, 30.0, 0.0,
        [
            _pad("1", "smd", "rect", -1.5, 0.0, 0.8, 0.6, 4, "VBUS"),
            _pad("2", "smd", "rect", 0.0, 0.0, 0.8, 0.6, 3, "VBAT"),
            _pad("3", "smd", "rect", 1.5, 0.0, 0.8, 0.6, 1, "GND"),
        ],
    ))

    # U3: XC6206 (SOT-23)
    fps.append(_fp(
        "Package_TO_SOT_SMD:SOT-23", "U3", "XC6206P332MR",
        10.0, 15.0, 0.0,
        [
            _pad("1", "smd", "rect", -1.5, 0.0, 0.8, 0.6, 3, "VBAT"),
            _pad("2", "smd", "rect", 0.0, 0.0, 0.8, 0.6, 2, "3V3"),
            _pad("3", "smd", "rect", 1.5, 0.0, 0.8, 0.6, 1, "GND"),
        ],
    ))

    # Resistors (0402, 1.0×0.5mm)
    def _r_fp(ref: str, value: str, x: float, y: float, net1: int, net2: int) -> list:
        return _fp("Resistor_SMD:R_0402_1005Metric", ref, value, x, y, 0.0, [
            _pad("1", "smd", "rect", -0.5, 0.0, 0.5, 0.5, net1, ""),
            _pad("2", "smd", "rect", 0.5, 0.0, 0.5, 0.5, net2, ""),
        ])

    # R1-R7
    fps.append(_r_fp("R1", "10k", 50.0, 25.0, 6, 2))      # KEY_VOL_UP pull-up
    fps.append(_r_fp("R2", "10k", 50.0, 22.0, 7, 2))      # KEY_VOL_DOWN pull-up
    fps.append(_r_fp("R3", "1k", 45.0, 15.0, 2, 8))       # LED_PWR
    fps.append(_r_fp("R4", "1k", 45.0, 12.0, 2, 9))       # LED_BT
    fps.append(_r_fp("R5", "100k", 15.0, 10.0, 3, 17))    # Battery div upper
    fps.append(_r_fp("R6", "100k", 15.0, 7.0, 17, 1))     # Battery div lower
    fps.append(_r_fp("R7", "2.2k", 40.0, 28.0, 2, 5))     # Mic bias

    # Capacitors (0402 or 0603)
    def _c_fp(ref: str, value: str, x: float, y: float, net1: int, net2: int) -> list:
        return _fp("Capacitor_SMD:C_0402_1005Metric", ref, value, x, y, 0.0, [
            _pad("1", "smd", "rect", -0.5, 0.0, 0.5, 0.5, net1, ""),
            _pad("2", "smd", "rect", 0.5, 0.0, 0.5, 0.5, net2, ""),
        ])

    fps.append(_c_fp("C1", "10uF", 25.0, 25.0, 2, 1))     # Bulk cap
    fps.append(_c_fp("C2", "100nF", 25.0, 22.0, 2, 1))    # Decoupling
    fps.append(_c_fp("C3", "100nF", 13.0, 18.0, 2, 1))    # LDO decoupling
    fps.append(_c_fp("C4", "1uF", 7.0, 18.0, 2, 1))       # LDO output
    fps.append(_c_fp("C5", "10uF", 42.0, 25.0, 5, 1))     # Mic coupling

    # LEDs (0603)
    fps.append(_fp("LED_SMD:LED_0603_1608Metric", "D1", "LED_RED", 45.0, 8.0, 0.0, [
        _pad("1", "smd", "rect", -0.8, 0.0, 0.8, 0.8, 1, "GND"),
        _pad("2", "smd", "rect", 0.8, 0.0, 0.8, 0.8, 8, "LED_PWR_GPIO5"),
    ]))
    fps.append(_fp("LED_SMD:LED_0603_1608Metric", "D2", "LED_BLUE", 45.0, 5.0, 0.0, [
        _pad("1", "smd", "rect", -0.8, 0.0, 0.8, 0.8, 1, "GND"),
        _pad("2", "smd", "rect", 0.8, 0.0, 0.8, 0.8, 9, "LED_BT_GPIO6"),
    ]))

    # Switches (tactile, 3×4mm)
    fps.append(_fp("Button_Switch_SMD:SW_SPST_TL3342", "SW1", "KEY_VOL_UP", 52.0, 25.0, 0.0, [
        _pad("1", "smd", "rect", -1.5, 0.0, 0.8, 0.6, 6, "KEY_VOL_UP_GPIO2"),
        _pad("2", "smd", "rect", 1.5, 0.0, 0.8, 0.6, 1, "GND"),
    ]))
    fps.append(_fp("Button_Switch_SMD:SW_SPST_TL3342", "SW2", "KEY_VOL_DOWN", 52.0, 20.0, 0.0, [
        _pad("1", "smd", "rect", -1.5, 0.0, 0.8, 0.6, 7, "KEY_VOL_DOWN_GPIO4"),
        _pad("2", "smd", "rect", 1.5, 0.0, 0.8, 0.6, 1, "GND"),
    ]))

    # Microphone (electret, 2 pads)
    fps.append(_fp("Audio:MIC_Electret", "MK1", "MIC_ELECTRET", 48.0, 32.0, 0.0, [
        _pad("1", "smd", "rect", -1.0, 0.0, 1.0, 1.0, 5, "ADC_MIC_GPIO1"),
        _pad("2", "smd", "rect", 1.0, 0.0, 1.0, 1.0, 1, "GND"),
    ]))

    # Battery connector (JST-PH 2pin)
    fps.append(_fp("Connector_JST:JST_PH_S2B-PH-K_1x02_P2.00mm_Horizontal", "BT1", "LiPo_3V7", 5.0, 35.0, 0.0, [
        _pad("1", "thru_hole", "circle", -1.0, 0.0, 1.5, 1.5, 3, "VBAT", 0.8),
        _pad("2", "thru_hole", "circle", 1.0, 0.0, 1.5, 1.5, 1, "GND", 0.8),
    ]))

    # Type-C connector (simplified, 6pin)
    fps.append(_fp("Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", "J1", "USB_TYPE-C", 5.0, 5.0, 0.0, [
        _pad("A1", "smd", "rect", -3.0, 0.0, 0.6, 1.2, 1, "GND"),
        _pad("A4", "smd", "rect", -1.5, 0.0, 0.6, 1.2, 4, "VBUS"),
        _pad("A5", "smd", "rect", -0.5, 0.0, 0.6, 1.2, 11, "USB_DM_GPIO19"),
        _pad("A6", "smd", "rect", 0.5, 0.0, 0.6, 1.2, 12, "USB_DP_GPIO20"),
        _pad("A9", "smd", "rect", 1.5, 0.0, 0.6, 1.2, 4, "VBUS"),
        _pad("A12", "smd", "rect", 3.0, 0.0, 0.6, 1.2, 1, "GND"),
    ]))

    return fps


def board_outline() -> list:
    """60mm × 40mm rectangular board outline."""
    return [
        "gr_rect",
        ["start", "0", "0"],
        ["end", "60", "40"],
        ["stroke", ["width", "0.1"], ["type", "default"]],
        ["fill", "none"],
        ["layer", "Edge.Cuts"],
        ["uuid", _uuid()],
    ]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_YAML = """\
project:
  name: "bluetooth_mic_board"
  description: "ESP32-S3 portable Bluetooth audio pickup board"
  mcu_profile: "libraries/mcu_profiles/esp32_s3.yaml"

requirements:
  - net_name: "ADC_MIC_GPIO1"
    required: true
    role: "analog"
  - net_name: "KEY_VOL_UP_GPIO2"
    required: true
    role: "gpio"
  - net_name: "KEY_VOL_DOWN_GPIO4"
    required: true
    role: "gpio"
  - net_name: "LED_PWR_GPIO5"
    required: true
    role: "gpio"
  - net_name: "LED_BT_GPIO6"
    required: true
    role: "gpio"
  - net_name: "VBATT_DIV_GPIO7"
    required: true
    role: "analog"
  - net_name: "USB_DM_GPIO19"
    required: true
    role: "high_speed"
  - net_name: "USB_DP_GPIO20"
    required: true
    role: "high_speed"
  - net_name: "3V3"
    required: true
    role: "power"
  - net_name: "GND"
    required: true
    role: "ground"
  - net_name: "VBAT"
    required: true
    role: "power"
  - net_name: "VBUS"
    required: false
    role: "power"

placement:
  pogo_array:
    rows: 3
    cols: 4
    pitch_mm: 2.54
    side: "bottom"
  strategy: "spread"

routing:
  keepout_margin_mm: 0.5
  trace_width_mm: 0.2
  via_diameter_mm: 0.6

protection:
  enabled: true
  default_type: "series_resistor"
  default_value: "100"
  default_package: "0402"
  per_net:
    - net_name: "ADC_MIC_GPIO1"
      type: "series_resistor"
      value: "100"
    - net_name: "VBATT_DIV_GPIO7"
      type: "series_resistor"
      value: "100"
    - net_name: "USB_DM_GPIO19"
      type: "ferrite_bead"
      value: "600@100MHz"
    - net_name: "USB_DP_GPIO20"
      type: "ferrite_bead"
      value: "600@100MHz"
"""


def main() -> None:
    out_dir = Path(__file__).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # Schematic
    sch = build_schematic()
    sch_text = serialize(sch.raw) + "\n"
    (out_dir / "main.kicad_sch").write_text(sch_text, encoding="utf-8")
    print(f"Wrote schematic: {out_dir / 'main.kicad_sch'}")

    # PCB
    pcb = build_pcb()
    pcb_text = serialize(pcb.raw) + "\n"
    (out_dir / "main.kicad_pcb").write_text(pcb_text, encoding="utf-8")
    print(f"Wrote PCB: {out_dir / 'main.kicad_pcb'}")

    # Config
    (out_dir / "config.yaml").write_text(CONFIG_YAML, encoding="utf-8")
    print(f"Wrote config: {out_dir / 'config.yaml'}")


if __name__ == "__main__":
    main()
