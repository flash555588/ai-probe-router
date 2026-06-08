"""Generate KiCad PCB constraints for the Audio Player project.

This script creates a KiCad .kicad_pcb constraint file with:
- Design rules (clearance, track width, via sizes)
- Impedance-controlled net classes
- Digital/Analog zone separation
- Differential pair rules
- Power net classes

Usage:
    python generate_constraints.py --output-dir .
    # Then open main.kicad_pcb in KiCad

Or import as a module:
    from generate_constraints import generate_full_pcb_skeleton
    pcb = generate_full_pcb_skeleton()
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ------------------------------------------------------------------
# Layer stack for JLCPCB 6-layer, 1.6mm total
# ------------------------------------------------------------------
@dataclass
class LayerStack:
    """6-layer stack-up."""

    total_thickness_mm: float = 1.6
    layers: list[dict[str, Any]] = field(default_factory=lambda: [
        {"name": "F.Cu", "type": "signal", "thickness_mm": 0.035},
        {"name": "In1.Cu", "type": "signal", "thickness_mm": 0.0175},
        {"name": "In2.Cu", "type": "power", "thickness_mm": 0.0175},
        {"name": "In3.Cu", "type": "power", "thickness_mm": 0.0175},
        {"name": "In4.Cu", "type": "power", "thickness_mm": 0.0175},
        {"name": "B.Cu", "type": "signal", "thickness_mm": 0.035},
    ])


# ------------------------------------------------------------------
# Design Rules
# ------------------------------------------------------------------
@dataclass
class DesignRules:
    """PCB design rules for 6-layer, 0.1mm min trace, JLCPCB capabilities."""

    min_trace_width_mm: float = 0.1
    min_trace_spacing_mm: float = 0.1
    min_via_drill_mm: float = 0.2
    min_via_size_mm: float = 0.4
    min_microvia_drill_mm: float = 0.1
    min_microvia_size_mm: float = 0.25
    max_board_width_mm: float = 75.0
    max_board_height_mm: float = 45.0
    surface_finish: str = "ENIG"
    via_in_pad: bool = True


# ------------------------------------------------------------------
# Net Classes
# ------------------------------------------------------------------
@dataclass
class NetClass:
    name: str
    trace_width_mm: float
    clearance_mm: float
    via_size_mm: float
    via_drill_mm: float
    diff_pair_width_mm: float | None = None
    diff_pair_gap_mm: float | None = None
    impedance_ohm: float | None = None
    notes: str = ""
    nets: list[str] = field(default_factory=list)


NET_CLASSES: list[NetClass] = [
    NetClass(
        name="Default",
        trace_width_mm=0.15,
        clearance_mm=0.15,
        via_size_mm=0.4,
        via_drill_mm=0.2,
        notes="Standard digital signals",
    ),
    NetClass(
        name="USB_DP_DM",
        trace_width_mm=0.15,
        clearance_mm=0.15,
        via_size_mm=0.4,
        via_drill_mm=0.2,
        diff_pair_width_mm=0.15,
        diff_pair_gap_mm=0.15,
        impedance_ohm=90.0,
        notes="USB 2.0 Full-Speed differential pair",
        nets=["USB_DP", "USB_DM"],
    ),
    NetClass(
        name="I2S_MCLK",
        trace_width_mm=0.15,
        clearance_mm=0.2,
        via_size_mm=0.4,
        via_drill_mm=0.2,
        impedance_ohm=50.0,
        notes="38.4MHz MCLK from TCXO to DAC, length under 10mm",
        nets=["I2S_MCK", "MCLK_38M4"],
    ),
    NetClass(
        name="I2S_DATA",
        trace_width_mm=0.15,
        clearance_mm=0.2,
        via_size_mm=0.4,
        via_drill_mm=0.2,
        impedance_ohm=50.0,
        notes="I2S BCLK/SD/WS, match lengths +-2mm",
        nets=["I2S_SCK", "I2S_SD", "I2S_WS"],
    ),
    NetClass(
        name="Analog_Audio",
        trace_width_mm=0.2,
        clearance_mm=0.3,
        via_size_mm=0.4,
        via_drill_mm=0.2,
        impedance_ohm=50.0,
        notes="DAC LPOUT/RPOUT to HP amp, L6 only, away from digital",
        nets=["DAC_L+", "DAC_L-", "DAC_R+", "DAC_R-", "HP_OUT_L", "HP_OUT_R"],
    ),
    NetClass(
        name="Power_3V3_D",
        trace_width_mm=0.5,
        clearance_mm=0.2,
        via_size_mm=0.5,
        via_drill_mm=0.25,
        notes="Digital 3.3V power distribution",
        nets=["3V3", "VDD_3V3_D", "+3.3V"],
    ),
    NetClass(
        name="Power_3V3_A",
        trace_width_mm=0.4,
        clearance_mm=0.2,
        via_size_mm=0.5,
        via_drill_mm=0.25,
        notes="Analog 3.3V, filtered from digital 3.3V via LC",
        nets=["3V3A", "VDD_3V3_A", "AVCC", "+3.3VA"],
    ),
    NetClass(
        name="Power_1V8",
        trace_width_mm=0.3,
        clearance_mm=0.2,
        via_size_mm=0.5,
        via_drill_mm=0.25,
        notes="ES9018K2M DVDD, separate LDO",
        nets=["1V8", "VDD_1V8", "DVDD", "+1.8V"],
    ),
    NetClass(
        name="Power_VBAT",
        trace_width_mm=0.6,
        clearance_mm=0.3,
        via_size_mm=0.6,
        via_drill_mm=0.3,
        notes="Battery power, high current for Class-D amps",
        nets=["VBAT", "+BATT", "PVDD"],
    ),
    NetClass(
        name="Power_5V",
        trace_width_mm=0.5,
        clearance_mm=0.2,
        via_size_mm=0.5,
        via_drill_mm=0.25,
        notes="USB VBUS input",
        nets=["VBUS", "VBUS_5V0", "+5V"],
    ),
    NetClass(
        name="GND_Digital",
        trace_width_mm=0.5,
        clearance_mm=0.2,
        via_size_mm=0.5,
        via_drill_mm=0.25,
        notes="Digital ground (L2, L4)",
        nets=["GND", "DGND", "VSS"],
    ),
    NetClass(
        name="GND_Analog",
        trace_width_mm=0.4,
        clearance_mm=0.3,
        via_size_mm=0.5,
        via_drill_mm=0.25,
        notes="Analog ground (L5), single-point tie to digital GND",
        nets=["AGND", "GND_A"],
    ),
    NetClass(
        name="SDIO",
        trace_width_mm=0.15,
        clearance_mm=0.15,
        via_size_mm=0.4,
        via_drill_mm=0.2,
        notes="SDIO CMD/CLK/D0-D3, match lengths +-1mm",
        nets=["SDIO_CMD", "SDIO_CLK", "SDIO_D0", "SDIO_D1", "SDIO_D2", "SDIO_D3"],
    ),
    NetClass(
        name="SPI_Flash",
        trace_width_mm=0.15,
        clearance_mm=0.15,
        via_size_mm=0.4,
        via_drill_mm=0.2,
        notes="SPI to W25Q128, short traces near MCU",
        nets=["SPI_SCK", "SPI_MISO", "SPI_MOSI", "FLASH_CS"],
    ),
    NetClass(
        name="I2C",
        trace_width_mm=0.15,
        clearance_mm=0.15,
        via_size_mm=0.4,
        via_drill_mm=0.2,
        notes="I2C for screen and joystick, 400kHz",
        nets=["I2C1_SCL", "I2C1_SDA", "I2C_SCL", "I2C_SDA"],
    ),
    NetClass(
        name="SWD_Debug",
        trace_width_mm=0.15,
        clearance_mm=0.15,
        via_size_mm=0.4,
        via_drill_mm=0.2,
        notes="SWDIO + SWCLK + NRST",
        nets=["SWDIO", "SWCLK", "NRST"],
    ),
    NetClass(
        name="Speaker_Out",
        trace_width_mm=0.5,
        clearance_mm=0.3,
        via_size_mm=0.5,
        via_drill_mm=0.25,
        notes="Class-D differential output, short + thick",
        nets=["SPK_L+", "SPK_L-", "SPK_R+", "SPK_R-"],
    ),
]


# ------------------------------------------------------------------
# Placement Zones
# ------------------------------------------------------------------
@dataclass
class KeepoutZone:
    name: str
    layer: str
    polygon_mm: list[tuple[float, float]]
    keepout: bool = True


PLACEMENT_ZONES: list[KeepoutZone] = [
    KeepoutZone(
        name="Digital_Region",
        layer="Cmts.User",
        polygon_mm=[
            (0.0, 22.5), (75.0, 22.5), (75.0, 45.0), (0.0, 45.0),
        ],
        keepout=False,
    ),
    KeepoutZone(
        name="Analog_Region",
        layer="Cmts.User",
        polygon_mm=[
            (0.0, 0.0), (75.0, 0.0), (75.0, 22.5), (0.0, 22.5),
        ],
        keepout=False,
    ),
    KeepoutZone(
        name="Isolation_Gap",
        layer="F.Cu",
        polygon_mm=[
            (0.0, 21.0), (75.0, 21.0), (75.0, 24.0), (0.0, 24.0),
        ],
    ),
]


# ------------------------------------------------------------------
# KiCad generators
# ------------------------------------------------------------------
def _all_nets() -> list[str]:
    nets: set[str] = set()
    for nc in NET_CLASSES:
        nets.update(nc.nets)
    return sorted(nets)


def _netclass_to_kicad(nc: NetClass) -> str:
    lines: list[str] = [
        f'  (net_class "{nc.name}" "{nc.notes}"',
        f'    (clearance {nc.clearance_mm})',
        f'    (trace_width {nc.trace_width_mm})',
        f'    (via_dia {nc.via_size_mm})',
        f'    (via_drill {nc.via_drill_mm})',
        '    (uvia_dia 0.3)',
        '    (uvia_drill 0.1)',
    ]
    if nc.diff_pair_width_mm is not None:
        lines.append(f'    (diff_pair_width {nc.diff_pair_width_mm})')
    if nc.diff_pair_gap_mm is not None:
        lines.append(f'    (diff_pair_gap {nc.diff_pair_gap_mm})')
    for net in nc.nets:
        lines.append(f'    (add_net "{net}")')
    lines.append("  )")
    return "\n".join(lines)


def _zone_to_kicad(z: KeepoutZone) -> str:
    pts = " ".join(f"(xy {x} {y})" for x, y in z.polygon_mm)
    keepout = ""
    if z.keepout:
        keepout = (
            "    (keepout (tracks not_allowed) (vias not_allowed) "
            "(pads not_allowed) (copperpour not_allowed) "
            "(footprints not_allowed))\n"
        )
    connect_pads = "no" if z.keepout else "yes"
    fill = "no" if not z.keepout else "yes"
    return (
        f'  (zone (net 0) (net_name "") (layers "{z.layer}") '
        f'(uuid "{uuid.uuid4()}")\n'
        f'    (name "{z.name}")\n'
        f'    (hatch edge 0.5)\n'
        f'    (connect_pads {connect_pads})\n'
        f'    (min_thickness 0.15)\n'
        f'{keepout}'
        f'    (fill {fill} (thermal_gap 0.5) (thermal_bridge_width 0.5))\n'
        f'    (polygon\n'
        f'      (pts\n'
        f'        {pts}\n'
        f'      )\n'
        f'    )\n'
        f'  )'
    )


def _nets_block() -> str:
    lines = ['  (net 0 "")']
    for idx, net in enumerate(_all_nets(), start=1):
        lines.append(f'  (net {idx} "{net}")')
    return "\n".join(lines)


def generate_full_pcb_skeleton() -> str:
    """Generate a complete minimal .kicad_pcb skeleton with constraints."""
    import uuid
    def _u():
        return str(uuid.uuid4())

    nets = _nets_block()
    netclasses = "\n".join(_netclass_to_kicad(nc) for nc in NET_CLASSES)
    zones = "\n".join(_zone_to_kicad(z) for z in PLACEMENT_ZONES)
    return f"""(kicad_pcb
  (version 20240108)
  (generator "pcbnew")
  (generator_version "8.0")
  (general
    (thickness 1.6)
    (legacy_teardrops no)
  )
  (paper "A4")
  (title_block
    (title "Audio Player / Handheld Console")
    (date "2026-06-08")
    (rev "v0.1")
    (company "DIY Audio Project")
  )
  (setup
    (pad_to_mask_clearance 0.05)
    (allow_soldermask_bridges_in_footprints no)
  )
  (layers
    (0 "F.Cu" signal)
    (1 "In1.Cu" signal)
    (2 "In2.Cu" signal)
    (3 "In3.Cu" signal)
    (4 "In4.Cu" signal)
    (31 "B.Cu" signal)
    (32 "B.Adhes" user "B.Adhesive")
    (33 "F.Adhes" user "F.Adhesive")
    (34 "B.Paste" user)
    (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user)
    (39 "F.Mask" user)
    (40 "Dwgs.User" user "User.Drawings")
    (41 "Cmts.User" user "User.Comments")
    (42 "Eco1.User" user "User.Eco1")
    (43 "Eco2.User" user "User.Eco2")
    (44 "Edge.Cuts" user)
    (45 "Margin" user)
    (46 "B.CrtYd" user "B.Courtyard")
    (47 "F.CrtYd" user "F.Courtyard")
    (48 "B.Fab" user)
    (49 "F.Fab" user)
  )
{nets}
{netclasses}
{zones}
  (gr_rect
    (start 0 0)
    (end 75 45)
    (stroke (width 0.1) (type default))
    (fill none)
    (layer "Edge.Cuts")
    (uuid "{_u()}")
  )
)
"""


def generate_constraint_report() -> dict[str, Any]:
    return {
        "net_classes": [
            {"name": nc.name, "trace_width_mm": nc.trace_width_mm,
             "clearance_mm": nc.clearance_mm, "impedance_ohm": nc.impedance_ohm,
             "nets": nc.nets, "notes": nc.notes}
            for nc in NET_CLASSES
        ],
        "placement_zones": [
            {"name": z.name, "layer": z.layer, "polygon_mm": z.polygon_mm}
            for z in PLACEMENT_ZONES
        ],
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Generate KiCad PCB constraints for Audio Player"
    )
    parser.add_argument(
        "--format", choices=["kicad", "json", "both"], default="both"
    )
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.format in ("kicad", "both"):
        pcb_path = args.output_dir / "main.kicad_pcb"
        pcb_path.write_text(generate_full_pcb_skeleton(), encoding="utf-8")
        print(f"Generated: {pcb_path}")

    if args.format in ("json", "both"):
        json_path = args.output_dir / "constraints.json"
        json_path.write_text(
            json.dumps(generate_constraint_report(), indent=2),
            encoding="utf-8",
        )
        print(f"Generated: {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
