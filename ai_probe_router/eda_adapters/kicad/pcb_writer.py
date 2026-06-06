"""Write testpoint/protection footprints and net declarations into a PCB."""

from __future__ import annotations

import uuid as _uuid
from pathlib import Path

from ...models.board import Board
from ...models.protection import ProtectionComponent
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


def add_protection_footprint(
    board: Board,
    src_net_name: str,
    probe_net_name: str,
    x: float,
    y: float,
    protection: ProtectionComponent,
    *,
    ref: str = "R?",
    side: str = "top",
) -> None:
    """Place a series resistor or ferrite bead footprint.

    Pad 1 connects to src_net_name (MCU side).
    Pad 2 connects to probe_net_name (probe side).
    Placed horizontally, offset from testpoint position.
    """
    layer = "F.Cu" if side == "top" else "B.Cu"
    silk = "F.SilkS" if side == "top" else "B.SilkS"
    fab = "F.Fab" if side == "top" else "B.Fab"
    mask = "F.Mask" if side == "top" else "B.Mask"

    src_net_id = board.nets.get(src_net_name)
    if src_net_id is None:
        src_net_id = board.next_net_id()
        board.nets[src_net_name] = src_net_id
        board.raw.append(["net", str(src_net_id), src_net_name])

    probe_net_id = board.nets.get(probe_net_name)
    if probe_net_id is None:
        probe_net_id = board.next_net_id()
        board.nets[probe_net_name] = probe_net_id
        board.raw.append(["net", str(probe_net_id), probe_net_name])

    uid = str(_uuid.uuid4())
    fp_name = protection.footprint_name

    # Pad spacing depends on package size (center-to-center)
    pad_spacing = {"0402": 0.625, "0603": 0.9, "0805": 1.1}
    half_span = pad_spacing.get(protection.package, 0.625)
    pad_w = {"0402": 0.6, "0603": 0.8, "0805": 1.0}
    pad_h = {"0402": 0.5, "0603": 0.75, "0805": 0.9}
    pw = pad_w.get(protection.package, 0.6)
    ph = pad_h.get(protection.package, 0.5)

    fp_node = [
        "footprint", fp_name,
        ["layer", layer],
        ["uuid", uid],
        ["at", str(x), str(y)],
        ["property", "Reference", ref,
         ["at", "0", str(-1.5), "0"],
         ["layer", silk],
         ["effects", ["font", ["size", "0.8", "0.8"], ["thickness", "0.12"]]]],
        ["property", "Value", protection.value,
         ["at", "0", str(1.5), "0"],
         ["layer", fab],
         ["effects", ["font", ["size", "0.8", "0.8"], ["thickness", "0.12"]]]],
        ["pad", "1", "smd", "roundrect",
         ["at", str(-half_span), "0"],
         ["size", str(pw), str(ph)],
         ["layers", layer, mask],
         ["roundrect_rratio", "0.25"],
         ["net", str(src_net_id), src_net_name]],
        ["pad", "2", "smd", "roundrect",
         ["at", str(half_span), "0"],
         ["size", str(pw), str(ph)],
         ["layers", layer, mask],
         ["roundrect_rratio", "0.25"],
         ["net", str(probe_net_id), probe_net_name]],
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


def add_keepout_zone(
    board: Board,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    layers: list[str] | None = None,
) -> None:
    """Add a rectangular keepout zone around a probe pad or connector.

    Default layers cover all copper and keepout layers.
    """
    if layers is None:
        layers = ["F.Cu", "B.Cu"]
    half_w = width / 2
    half_h = height / 2
    uid = str(_uuid.uuid4())
    zone_node = [
        "zone",
        ["net", "0"],
        ["net_name", ""],
        ["layers"] + layers,
        ["uuid", uid],
        ["hatch", "edge", "0.5"],
        ["connect_pads", "no"],
        ["min_thickness", "0.25"],
        ["keepout",
         ["tracks", "not_allowed"],
         ["vias", "not_allowed"],
         ["pads", "not_allowed"],
         ["copperpour", "not_allowed"],
         ["footprints", "not_allowed"]],
        ["fill", "yes"],
        ["polygon",
         ["pts",
          ["xy", str(x - half_w), str(y - half_h)],
          ["xy", str(x + half_w), str(y - half_h)],
          ["xy", str(x + half_w), str(y + half_h)],
          ["xy", str(x - half_w), str(y + half_h)]]],
    ]
    board.raw.append(zone_node)


def add_fiducial_footprint(
    board: Board,
    x: float,
    y: float,
    *,
    ref: str = "FID?",
    diameter_mm: float = 1.0,
    mask_diameter_mm: float = 2.0,
) -> None:
    """Place a fiducial marker (copper circle with larger mask opening)."""
    uid = str(_uuid.uuid4())
    fp_name = "Fiducial:Fiducial_{:.1f}mm_Mask{:.1f}mm".format(
        diameter_mm, mask_diameter_mm,
    )
    fp_node = [
        "footprint", fp_name,
        ["layer", "F.Cu"],
        ["uuid", uid],
        ["at", str(x), str(y)],
        ["property", "Reference", ref,
         ["at", str(x), str(y - 2), "0"],
         ["layer", "F.SilkS"],
         ["effects", ["font", ["size", "1", "1"], ["thickness", "0.15"]]]],
        ["property", "Value", f"FID_{ref}",
         ["at", str(x), str(y + 2), "0"],
         ["layer", "F.Fab"],
         ["effects", ["font", ["size", "1", "1"], ["thickness", "0.15"]]]],
        ["pad", "", "smd", "circle",
         ["at", "0", "0"],
         ["size", str(diameter_mm), str(diameter_mm)],
         ["layers", "F.Cu", "F.Mask"],
         ["solder_mask_margin", str((mask_diameter_mm - diameter_mm) / 2)]],
    ]
    board.raw.append(fp_node)


def add_tooling_hole_footprint(
    board: Board,
    x: float,
    y: float,
    *,
    ref: str = "TH?",
    drill_mm: float = 3.2,
    size_mm: float = 3.2,
) -> None:
    """Place a non-plated tooling/mounting hole."""
    uid = str(_uuid.uuid4())
    fp_node = [
        "footprint", f"MountingHole:MountingHole_{drill_mm}mm",
        ["layer", "Edge.Cuts"],
        ["uuid", uid],
        ["at", str(x), str(y)],
        ["property", "Reference", ref,
         ["at", str(x), str(y - 2), "0"],
         ["layer", "F.SilkS"],
         ["effects", ["font", ["size", "1", "1"], ["thickness", "0.15"]]]],
        ["property", "Value", f"MOUNT_{ref}",
         ["at", str(x), str(y + 2), "0"],
         ["layer", "F.Fab"],
         ["effects", ["font", ["size", "1", "1"], ["thickness", "0.15"]]]],
        ["pad", "", "np_thru_hole", "circle",
         ["at", "0", "0"],
         ["size", str(size_mm), str(size_mm)],
         ["drill", str(drill_mm)],
         ["layers", "*.Cu", "*.Mask"]],
    ]
    board.raw.append(fp_node)


def write_pcb(board: Board, path: str | Path) -> None:
    text = serialize(board.raw)
    Path(path).write_text(text, encoding="utf-8")
