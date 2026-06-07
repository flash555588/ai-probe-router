"""Write testpoint/protection footprints and net declarations into a PCB."""

from __future__ import annotations

import math
import uuid as _uuid
from pathlib import Path

from ...models.board import Board, Footprint, Pad
from ...models.protection import ProtectionComponent
from ...solvers.pin_mapper import PinAssignment
from ..kicad.sexpr import QuotedStr, serialize


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
) -> Footprint:
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

    fp_name = "TestPoint:TestPoint_Pad_D{:.1f}mm".format(pad_diameter)
    fp_node = [
        "footprint", fp_name,
        ["layer", layer],
        ["uuid", uid],
        ["at", str(x), str(y)],
        ["property", "Reference", ref,
         ["at", str(x), str(y - 2), "0"],
         ["layer", silk],
         ["hide", "yes"],
         ["effects", ["font", ["size", "1", "1"], ["thickness", "0.15"]]]],
        ["property", "Value", label or f"TP_{net_name}",
         ["at", str(x), str(y + 2), "0"],
         ["layer", fab],
         ["effects", ["font", ["size", "1", "1"], ["thickness", "0.15"]]]],
        ["pad", QuotedStr("1"), "smd", "circle",
         ["at", "0", "0"],
         ["size", str(pad_diameter), str(pad_diameter)],
         ["layers", layer, mask],
         ["net", str(net_id), net_name]],
    ]
    board.raw.append(fp_node)
    model_fp = Footprint(
        ref=ref,
        value=label or f"TP_{net_name}",
        lib_id=fp_name,
        x=x,
        y=y,
        layer=layer,
        uuid=uid,
        pads=[Pad(
            number="1",
            pad_type="smd",
            shape="circle",
            x=x,
            y=y,
            width=pad_diameter,
            height=pad_diameter,
            net_name=net_name,
            net_id=net_id,
            layers=[layer, mask],
        )],
    )
    board.footprints.append(model_fp)
    return model_fp


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
    rotation: float = 0.0,
) -> Footprint:
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

    # half_span, width, height in mm for practical KiCad-style SMD pads.
    pad_specs = {
        "0402": (0.48, 0.56, 0.62),
        "0603": (0.75, 0.80, 0.95),
        "0805": (0.95, 1.00, 1.20),
    }
    half_span, pw, ph = pad_specs.get(protection.package, pad_specs["0402"])

    fp_node = [
        "footprint", fp_name,
        ["layer", layer],
        ["uuid", uid],
        ["at", str(x), str(y), str(rotation)],
        ["property", "Reference", ref,
         ["at", "0", str(-1.5), "0"],
         ["layer", silk],
         ["hide", "yes"],
         ["effects", ["font", ["size", "0.8", "0.8"], ["thickness", "0.12"]]]],
        ["property", "Value", QuotedStr(protection.value),
         ["at", "0", str(1.5), "0"],
         ["layer", fab],
         ["effects", ["font", ["size", "0.8", "0.8"], ["thickness", "0.12"]]]],
        ["pad", QuotedStr("1"), "smd", "roundrect",
         ["at", str(-half_span), "0"],
         ["size", str(pw), str(ph)],
         ["layers", layer, mask],
         ["roundrect_rratio", "0.25"],
         ["net", str(src_net_id), src_net_name]],
        ["pad", QuotedStr("2"), "smd", "roundrect",
         ["at", str(half_span), "0"],
         ["size", str(pw), str(ph)],
         ["layers", layer, mask],
         ["roundrect_rratio", "0.25"],
         ["net", str(probe_net_id), probe_net_name]],
    ]
    board.raw.append(fp_node)
    p1x, p1y = _rotate_local(-half_span, 0.0, rotation, x, y)
    p2x, p2y = _rotate_local(half_span, 0.0, rotation, x, y)
    model_fp = Footprint(
        ref=ref,
        value=protection.value,
        lib_id=fp_name,
        x=x,
        y=y,
        rotation=rotation,
        layer=layer,
        uuid=uid,
        pads=[
            Pad(
                number="1",
                pad_type="smd",
                shape="roundrect",
                x=p1x,
                y=p1y,
                width=pw,
                height=ph,
                net_name=src_net_name,
                net_id=src_net_id,
                layers=[layer, mask],
                local_x=-half_span,
                rotation=rotation,
            ),
            Pad(
                number="2",
                pad_type="smd",
                shape="roundrect",
                x=p2x,
                y=p2y,
                width=pw,
                height=ph,
                net_name=probe_net_name,
                net_id=probe_net_id,
                layers=[layer, mask],
                local_x=half_span,
                rotation=rotation,
            ),
        ],
    )
    board.footprints.append(model_fp)
    return model_fp


def add_track_segment(
    board: Board,
    net_name: str,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    width: float = 0.15,
    side: str = "top",
) -> None:
    net_id = board.nets.get(net_name)
    if net_id is None:
        net_id = board.next_net_id()
        board.nets[net_name] = net_id
        board.raw.append(["net", str(net_id), net_name])

    layer = "F.Cu" if side == "top" else "B.Cu"
    board.raw.append([
        "segment",
        ["start", str(x1), str(y1)],
        ["end", str(x2), str(y2)],
        ["width", str(width)],
        ["layer", layer],
        ["net", str(net_id)],
        ["uuid", str(_uuid.uuid4())],
    ])


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

    pitch_name = _format_pitch_for_library(pitch)
    lib_name = (
        f"Connector_PinHeader_{pitch_name}mm:"
        f"PinHeader_{rows}x{pins_per_row}_P{pitch_name}mm_Vertical"
    )

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
        pad_num = QuotedStr(str(a.pin_index + 1))
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
            "pad", QuotedStr(str(i + 1)), "thru_hole", "circle",
            ["at", str(px), str(py)],
            ["size", "1.7", "1.7"],
            ["drill", "1.0"],
            ["layers", "*.Cu", mask],
        ]
        fp_node.append(pad_node)

    board.raw.append(fp_node)
    model_pads: list[Pad] = []
    for i in range(total):
        row = i // pins_per_row
        col = i % pins_per_row
        px = col * pitch
        py = row * pitch
        assignment = next((a for a in assignments if a.pin_index == i), None)
        net_name = assignment.net_name if assignment else ""
        net_id = board.nets.get(net_name, 0) if net_name else 0
        model_pads.append(Pad(
            number=str(i + 1),
            pad_type="thru_hole",
            shape="circle",
            x=x + px,
            y=y + py,
            width=1.7,
            height=1.7,
            drill=1.0,
            net_name=net_name,
            net_id=net_id,
            layers=["*.Cu", mask],
            local_x=px,
            local_y=py,
        ))
    board.footprints.append(Footprint(
        ref=ref,
        value=f"CONN_{ref}",
        lib_id=lib_name,
        x=x,
        y=y,
        layer=layer,
        uuid=uid,
        pads=model_pads,
    ))


def add_keepout_zone(
    board: Board,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    layers: list[str] | None = None,
    tracks_allowed: bool = True,
    vias_allowed: bool = True,
    pads_allowed: bool = True,
    copperpour_allowed: bool = False,
    footprints_allowed: bool = True,
) -> None:
    """Add a rectangular keepout zone around a probe pad or connector.

    Default layers cover all copper and keepout layers.
    """
    if layers is None:
        layers = ["F.Cu", "B.Cu"]
    half_w = width / 2
    half_h = height / 2
    uid = str(_uuid.uuid4())
    def _permission(allowed: bool) -> str:
        return "allowed" if allowed else "not_allowed"

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
         ["tracks", _permission(tracks_allowed)],
         ["vias", _permission(vias_allowed)],
         ["pads", _permission(pads_allowed)],
         ["copperpour", _permission(copperpour_allowed)],
         ["footprints", _permission(footprints_allowed)]],
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
        ["pad", QuotedStr(""), "smd", "circle",
         ["at", "0", "0"],
         ["size", str(diameter_mm), str(diameter_mm)],
         ["layers", "F.Cu", "F.Mask"],
         ["solder_mask_margin", str((mask_diameter_mm - diameter_mm) / 2)]],
    ]
    board.raw.append(fp_node)
    board.footprints.append(Footprint(
        ref=ref,
        value=f"FID_{ref}",
        lib_id=fp_name,
        x=x,
        y=y,
        layer="F.Cu",
        uuid=uid,
        pads=[Pad(
            number="",
            pad_type="smd",
            shape="circle",
            x=x,
            y=y,
            width=diameter_mm,
            height=diameter_mm,
            layers=["F.Cu", "F.Mask"],
        )],
    ))


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
        ["pad", QuotedStr(""), "np_thru_hole", "circle",
         ["at", "0", "0"],
         ["size", str(size_mm), str(size_mm)],
         ["drill", str(drill_mm)],
         ["layers", "*.Cu", "*.Mask"]],
    ]
    board.raw.append(fp_node)
    board.footprints.append(Footprint(
        ref=ref,
        value=f"MOUNT_{ref}",
        lib_id=f"MountingHole:MountingHole_{drill_mm}mm",
        x=x,
        y=y,
        layer="Edge.Cuts",
        uuid=uid,
        pads=[Pad(
            number="",
            pad_type="np_thru_hole",
            shape="circle",
            x=x,
            y=y,
            width=size_mm,
            height=size_mm,
            drill=drill_mm,
            layers=["*.Cu", "*.Mask"],
        )],
    ))


def add_net_class(
    board: Board,
    name: str,
    description: str = "",
    *,
    clearance: float = 0.15,
    trace_width: float = 0.15,
    via_dia: float = 0.8,
    via_drill: float = 0.4,
    uvia_dia: float = 0.3,
    uvia_drill: float = 0.1,
    diff_pair_width: float | None = None,
    diff_pair_gap: float | None = None,
) -> None:
    """Insert or update a net_class at root level (KiCad 10 compatible)."""
    class_node = [
        "net_class", QuotedStr(name), QuotedStr(description),
        ["clearance", str(clearance)],
        ["trace_width", str(trace_width)],
        ["via_dia", str(via_dia)],
        ["via_drill", str(via_drill)],
        ["uvia_dia", str(uvia_dia)],
        ["uvia_drill", str(uvia_drill)],
    ]
    if diff_pair_width is not None:
        class_node.append(["diff_pair_width", str(diff_pair_width)])
    if diff_pair_gap is not None:
        class_node.append(["diff_pair_gap", str(diff_pair_gap)])

    # Remove existing net_class with same name from root level
    board.raw[:] = [
        n for n in board.raw
        if not (isinstance(n, list) and len(n) > 1 and n[0] == "net_class" and n[1] == name)
    ]

    # Insert after last net node (or after setup/layers)
    insert_at = 2
    for i, node in enumerate(board.raw):
        if isinstance(node, list) and len(node) > 0 and node[0] in (
            "general", "paper", "layers", "setup", "net",
        ):
            insert_at = i + 1
    board.raw.insert(insert_at, class_node)


def _rotate_local(
    local_x: float,
    local_y: float,
    rotation: float,
    origin_x: float,
    origin_y: float,
) -> tuple[float, float]:
    rad = math.radians(rotation)
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)
    return (
        origin_x + local_x * cos_r + local_y * sin_r,
        origin_y - local_x * sin_r + local_y * cos_r,
    )


def _format_pitch_for_library(pitch: float) -> str:
    return f"{pitch:.2f}".rstrip("0").rstrip(".")


def write_pcb(board: Board, path: str | Path) -> None:
    text = serialize(board.raw) + "\n"
    Path(path).write_text(text, encoding="utf-8")
