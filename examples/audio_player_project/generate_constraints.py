"""Generate KiCad PCB constraints for the Audio Player project.

This script creates a KiCad .kicad_pcb constraint file with:
- Design rules (clearance, track width, via sizes)
- Impedance-controlled net classes
- Digital/Analog zone separation
- Differential pair rules
- Power net classes

Usage:
    python generate_constraints.py > constraints.kicad_pcb
    # Then copy the relevant sections into your main.kicad_pcb

Or import as a plugin module:
    from generate_constraints import generate_pcb_constraints
    pcb = generate_pcb_constraints()
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


# ------------------------------------------------------------------
# Layer stack for JLCPCB 6-layer, 1.6mm total
# ------------------------------------------------------------------
@dataclass
class LayerStack:
    """6-layer stack-up: L1-Signal, L2-GND, L3-Signal, L4-PWR, L5-GND, L6-Signal."""

    total_thickness_mm: float = 1.6
    layers: list[dict[str, Any]] = field(default_factory=lambda: [
        {
            "name": "F.Cu", "type": "signal",
            "thickness_mm": 0.035,
            "purpose": "High-speed digital + components",
        },
        {
            "name": "In1.Cu", "type": "signal",
            "thickness_mm": 0.0175,
            "purpose": "I2S / SDIO / internal routing",
        },
        {
            "name": "In2.Cu", "type": "power",
            "thickness_mm": 0.0175,
            "purpose": "3V3_D / 3V3_A / 1V8 / VBAT planes",
        },
        {
            "name": "In3.Cu", "type": "power",
            "thickness_mm": 0.0175,
            "purpose": "GND plane (digital)",
        },
        {
            "name": "In4.Cu", "type": "power",
            "thickness_mm": 0.0175,
            "purpose": "GND plane (analog)",
        },
        {
            "name": "B.Cu", "type": "signal",
            "thickness_mm": 0.035,
            "purpose": "Analog audio + bottom components",
        },
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
    min_hole_to_hole_mm: float = 0.25
    min_annular_ring_mm: float = 0.1
    max_board_width_mm: float = 75.0
    max_board_height_mm: float = 45.0
    edge_keepout_mm: float = 2.0
    solder_mask_color: str = "black"
    silkscreen_color: str = "white"
    surface_finish: str = "ENIG"
    via_in_pad: bool = True
    impedance_controlled: bool = True


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
        notes="38.4MHz MCLK from TCXO to DAC, length < 10mm",
        nets=["I2S_MCK", "MCLK_38M4"],
    ),
    NetClass(
        name="I2S_DATA",
        trace_width_mm=0.15,
        clearance_mm=0.2,
        via_size_mm=0.4,
        via_drill_mm=0.2,
        impedance_ohm=50.0,
        notes="I2S BCLK/SD/WS, match lengths ±2mm",
        nets=["I2S_SCK", "I2S_SD", "I2S_WS"],
    ),
    NetClass(
        name="Analog_Audio",
        trace_width_mm=0.2,
        clearance_mm=0.3,
        via_size_mm=0.4,
        via_drill_mm=0.2,
        impedance_ohm=50.0,
        notes="DAC LPOUT/RPOUT → HP amp, L6 only,远离数字",
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
        notes="Digital ground (L2, L4)" ,
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
        notes="SDIO CMD/CLK/D0-D3, match lengths ±1mm",
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
# Placement Zones (Digital / Analog separation)
# ------------------------------------------------------------------
@dataclass
class KeepoutZone:
    """A PCB keepout or placement zone."""

    name: str
    layer: str
    purpose: str
    polygon_mm: list[tuple[float, float]]  # Clockwise from bottom-left
    allowed_nets: list[str] = field(default_factory=list)
    forbidden_nets: list[str] = field(default_factory=list)


PLACEMENT_ZONES: list[KeepoutZone] = [
    KeepoutZone(
        name="Digital_Region",
        layer="*.Cu",
        purpose="High-speed digital: MCU, Flash, USB, TF, Screen FPC",
        polygon_mm=[
            (0.0, 22.5),
            (75.0, 22.5),
            (75.0, 45.0),
            (0.0, 45.0),
        ],
        allowed_nets=["3V3", "GND", "VBUS", "USB_DP", "USB_DM", "SDIO_*", "SPI_*", "I2C_*"],
        forbidden_nets=["DAC_L+", "DAC_L-", "DAC_R+", "DAC_R-", "AGND", "3V3A"],
    ),
    KeepoutZone(
        name="Analog_Region",
        layer="*.Cu",
        purpose="Audio analog: DAC, HP amp, TCXO",
        polygon_mm=[
            (0.0, 0.0),
            (75.0, 0.0),
            (75.0, 22.5),
            (0.0, 22.5),
        ],
        allowed_nets=["3V3A", "1V8", "AGND", "DAC_L+", "DAC_L-", "DAC_R+", "DAC_R-", "MCLK_38M4"],
        forbidden_nets=["USB_DP", "USB_DM", "SDIO_CLK", "SPI_SCK"],
    ),
    KeepoutZone(
        name="Isolation_Gap",
        layer="F.Cu",
        purpose="3mm gap between digital and analog, no traces crossing",
        polygon_mm=[
            (0.0, 21.0),
            (75.0, 21.0),
            (75.0, 24.0),
            (0.0, 24.0),
        ],
        forbidden_nets=["*"],  # No traces allowed in isolation gap on top layer
    ),
]


# ------------------------------------------------------------------
# Constraint summary
# ------------------------------------------------------------------
@dataclass
class ConstraintSummary:
    project_name: str = "Audio_Player_v0.1"
    board_size_mm: tuple[float, float] = (75.0, 45.0)
    layer_count: int = 6
    min_trace_mm: float = 0.1
    min_spacing_mm: float = 0.1
    via_in_pad: bool = True
    impedance_control: bool = True
    digital_analog_split: bool = True
    net_class_count: int = 0
    placement_zone_count: int = 0


# ------------------------------------------------------------------
# KiCad S-expression generators
# ------------------------------------------------------------------
def _indent(level: int) -> str:
    return "  " * level


def _netclass_to_kicad(nc: NetClass) -> str:
    """Generate KiCad net class S-expression."""
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
    """Generate KiCad zone S-expression (keepout)."""
    pts = " ".join(f"(xy {x} {y})" for x, y in z.polygon_mm)
    keepout = (
        "    (keepout (tracks not_allowed) (vias not_allowed) "
        "(pads not_allowed) (copperpour not_allowed) "
        "(footprints not_allowed))\n"
    )
    return (
        f'  (zone (net 0) (net_name "") (layers "{z.layer}") '
        f'(tstamp "{z.name.lower()}")\n'
        f'    (name "{z.name}")\n'
        f'    (hatch edge 0.5)\n'
        f'    (connect_pads no)\n'
        f'    (min_thickness 0.15)\n'
        f'{keepout}'
        f'    (fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5))\n'
        f'    (polygon\n'
        f'      (pts\n'
        f'        {pts}\n'
        f'      )\n'
        f'    )\n'
        f'  )'
    )


def generate_kicad_netclasses() -> str:
    """Return a string of KiCad net class definitions."""
    header = "  ;; === Auto-generated net classes (Audio Player) ==="
    body = "\n".join(_netclass_to_kicad(nc) for nc in NET_CLASSES)
    return f"{header}\n{body}"


def generate_kicad_zones() -> str:
    """Return a string of KiCad zone definitions."""
    header = "  ;; === Auto-generated placement zones (Digital/Analog split) ==="
    body = "\n".join(_zone_to_kicad(z) for z in PLACEMENT_ZONES)
    return f"{header}\n{body}"


def generate_design_rules_block() -> str:
    """Generate the KiCad design rules block."""
    dr = DesignRules()
    return f"""  (setup
    (pad_to_mask_clearance 0.05)
    (allow_soldermask_bridges_in_footprints no)
    (pcbplotparams
      (layerselection 0x00010fc_ffffffff)
      (plot_on_all_layers_selection 0x0000000_00000000)
      (disableapertmacros no)
      (usegerberextensions no)
      (usegerberattributes yes)
      (usegerberadvancedattributes yes)
      (creategerberjobfile yes)
      (dashed_line_dash_ratio 12.000000)
      (dashed_line_gap_ratio 3.000000)
      (svgprecision 4)
      (plotframeref no)
      (viasonmask no)
      (mode 1)
      (useauxorigin no)
      (hpglpennumber 1)
      (hpglpenspeed 20)
      (hpglpendiameter 15.000000)
      (pdf_front_fp_property_popups yes)
      (pdf_back_fp_property_popups yes)
      (dxfpolygonmode yes)
      (dxfimperialunits yes)
      (dxfusepcbnewfont yes)
      (psnegative no)
      (psa4output no)
      (plotreference yes)
      (plotvalue yes)
      (plotfptext yes)
      (plotinvisibletext no)
      (sketchpadsonfab no)
      (subtractmaskfromsilk no)
      (outputformat 1)
      (mirror no)
      (drillshape 1)
      (scaleselection 1)
      (outputdirectory "")
    )
  )
  ;; === Design Rules ===
  ;; Min trace: {dr.min_trace_width_mm} mm
  ;; Min spacing: {dr.min_trace_spacing_mm} mm
  ;; Min via: {dr.min_via_size_mm} mm / {dr.min_via_drill_mm} mm drill
  ;; Board: {dr.max_board_width_mm} x {dr.max_board_height_mm} mm
  ;; Surface finish: {dr.surface_finish}
  ;; Via-in-pad: {dr.via_in_pad}
"""


def generate_full_pcb_skeleton() -> str:
    """Generate a complete minimal .kicad_pcb skeleton with constraints."""
    netclasses = generate_kicad_netclasses()
    zones = generate_kicad_zones()
    setup = generate_design_rules_block()
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
{setup}
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
{netclasses}
{zones}
  ;; === Board Edge ===
  (gr_line (start 0 0) (end 75 0) (layer "Edge.Cuts") (width 0.1))
  (gr_line (start 75 0) (end 75 45) (layer "Edge.Cuts") (width 0.1))
  (gr_line (start 75 45) (end 0 45) (layer "Edge.Cuts") (width 0.1))
  (gr_line (start 0 45) (end 0 0) (layer "Edge.Cuts") (width 0.1))

  ;; === Digital/Analog split marker ===
  (dimension
    (type aligned)
    (layer "Dwgs.User")
    (pts (xy 2 22.5) (xy 73 22.5))
    (height -3)
    (gr_text "DIGITAL / ANALOG SPLIT" (at 37.5 18) (layer "Dwgs.User")
      (effects (font (size 2 2)))
    )
    (style (thickness 0.15) (arrow_length 1) (text_position_mode 0))
  )
)
"""


def generate_constraint_report() -> dict[str, Any]:
    """Generate a JSON-serializable constraint summary."""
    summary = ConstraintSummary(
        net_class_count=len(NET_CLASSES),
        placement_zone_count=len(PLACEMENT_ZONES),
    )
    return {
        "project": asdict(summary),
        "layer_stack": asdict(LayerStack()),
        "design_rules": asdict(DesignRules()),
        "net_classes": [
            {
                "name": nc.name,
                "trace_width_mm": nc.trace_width_mm,
                "clearance_mm": nc.clearance_mm,
                "impedance_ohm": nc.impedance_ohm,
                "nets": nc.nets,
                "notes": nc.notes,
            }
            for nc in NET_CLASSES
        ],
        "placement_zones": [
            {
                "name": z.name,
                "layer": z.layer,
                "purpose": z.purpose,
                "polygon_mm": z.polygon_mm,
            }
            for z in PLACEMENT_ZONES
        ],
    }


def main() -> int:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate KiCad PCB constraints for Audio Player project"
    )
    parser.add_argument(
        "--format",
        choices=["kicad", "json", "both"],
        default="both",
        help="Output format (default: both)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Directory to write output files",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.format in ("kicad", "both"):
        pcb_path = args.output_dir / "main.kicad_pcb"
        pcb_path.write_text(generate_full_pcb_skeleton(), encoding="utf-8")
        print(f"Generated: {pcb_path}")

        netclass_path = args.output_dir / "netclasses.kicad_pcb"
        netclass_path.write_text(generate_kicad_netclasses(), encoding="utf-8")
        print(f"Generated: {netclass_path}")

        zones_path = args.output_dir / "zones.kicad_pcb"
        zones_path.write_text(generate_kicad_zones(), encoding="utf-8")
        print(f"Generated: {zones_path}")

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
