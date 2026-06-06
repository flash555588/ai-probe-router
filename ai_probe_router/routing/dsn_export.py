"""Export a Board to a Specctra/Electra DSN file for autorouting."""

from __future__ import annotations

from pathlib import Path

from ..models.board import Board


def export_dsn(board: Board, path: str | Path) -> None:
    """Write a minimal DSN file from the board model.

    Includes board outline, netlist, placement, and basic design rules.
    """
    lines = ['(pcb "ai_probe_router_export"']
    lines.append("  (parser")
    lines.append('    (string_quote ")')
    lines.append("    (space_in_quoted_tokens on)")
    lines.append('    (host_cad "KiCad")')
    lines.append("  )")
    lines.append("  (resolution um 10)")
    lines.append("  (unit um)")

    _write_structure(lines, board)
    _write_placement(lines, board)
    _write_library(lines, board)
    _write_network(lines, board)

    lines.append(")")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def _write_structure(lines: list[str], board: Board) -> None:
    lines.append("  (structure")
    bounds = board.board_bounds()
    if bounds:
        # Board outline as boundary path (clockwise)
        pts = [
            (bounds.min_x, bounds.min_y),
            (bounds.max_x, bounds.min_y),
            (bounds.max_x, bounds.max_y),
            (bounds.min_x, bounds.max_y),
        ]
        pt_str = " ".join(f"{_um(x)} {_um(y)}" for x, y in pts + [pts[0]])
        lines.append(f"    (boundary (path signal 0 {pt_str}))")

    lines.append('    (layer TOP (type signal))')
    lines.append('    (layer BOTTOM (type signal))')
    lines.append("    (rule (width 150))")
    lines.append("    (rule (clearance 150))")
    lines.append("  )")


def _write_placement(lines: list[str], board: Board) -> None:
    lines.append("  (placement")
    for fp in board.footprints:
        side = "front" if fp.layer in ("F.Cu", "top") else "back"
        rot = f" {fp.rotation:.0f}" if fp.rotation else ""
        lines.append(
            f'    (component "{fp.lib_id}"'
            f' (place "{fp.ref}" {_um(fp.x)} {_um(fp.y)} {side}{rot}))'
        )
    lines.append("  )")


def _write_library(lines: list[str], board: Board) -> None:
    lines.append("  (library")
    for fp in board.footprints:
        if not fp.pads:
            continue
        lines.append(f'    (image "{fp.lib_id}"')
        # Simple rectangular outline around pads (relative to footprint origin)
        px = [p.local_x for p in fp.pads]
        py = [p.local_y for p in fp.pads]
        if px and py:
            min_x, max_x = min(px), max(px)
            min_y, max_y = min(py), max(py)
            pad = fp.pads[0]
            w = pad.width
            h = pad.height
            corners = [
                (min_x - w / 2, min_y - h / 2),
                (max_x + w / 2, min_y - h / 2),
                (max_x + w / 2, max_y + h / 2),
                (min_x - w / 2, max_y + h / 2),
            ]
            c_str = " ".join(f"{_um(cx)} {_um(cy)}" for cx, cy in corners + [corners[0]])
            lines.append(f'      (outline (path signal 0 {c_str}))')
        for pad in fp.pads:
            lines.append(
                f'      (pin "{pad.number}" {_um(pad.local_x)} {_um(pad.local_y)})'
            )
        lines.append("    )")
    lines.append("  )")


def _write_network(lines: list[str], board: Board) -> None:
    lines.append("  (network")
    net_pins: dict[str, list[str]] = {}
    for fp in board.footprints:
        for pad in fp.pads:
            if not pad.net_name:
                continue
            key = pad.net_name
            net_pins.setdefault(key, [])
            net_pins[key].append(f'"{fp.ref}-{pad.number}"')

    for net_name, pins in sorted(net_pins.items()):
        if net_name == "" or not pins:
            continue
        pin_str = " ".join(pins)
        lines.append(f'    (net "{net_name}" (pins {pin_str}))')
    lines.append("  )")


def _um(mm: float) -> int:
    """Convert millimeters to integer micrometers."""
    return int(round(mm * 1000))
