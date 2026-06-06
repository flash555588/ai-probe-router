"""Parse KiCad .kicad_pcb files into Board model."""

from __future__ import annotations

from pathlib import Path

from ...models.board import Board, EdgeSegment, Footprint, Pad
from ..kicad.sexpr import parse


def parse_pcb(path: str | Path) -> Board:
    text = Path(path).read_text(encoding="utf-8")
    tree = parse(text)
    if not isinstance(tree, list) or tree[0] != "kicad_pcb":
        raise ValueError(f"Not a KiCad PCB: {path}")
    nets = _extract_nets(tree)
    footprints = _extract_footprints(tree, nets)
    edges = _extract_edges(tree)
    return Board(footprints=footprints, nets=nets, edges=edges, raw=tree)


def _extract_nets(tree: list) -> dict[str, int]:
    nets: dict[str, int] = {}
    for node in tree[1:]:
        if isinstance(node, list) and node[0] == "net" and len(node) >= 3:
            net_id = int(node[1])
            net_name = str(node[2])
            nets[net_name] = net_id
    return nets


def _extract_footprints(tree: list, nets: dict[str, int]) -> list[Footprint]:
    results: list[Footprint] = []
    for node in tree[1:]:
        if isinstance(node, list) and node[0] == "footprint":
            fp = _parse_footprint(node, nets)
            if fp:
                results.append(fp)
    return results


def _parse_footprint(node: list, nets: dict[str, int]) -> Footprint | None:
    lib_id = node[1] if len(node) > 1 and isinstance(node[1], str) else ""
    at = _find_list(node, "at")
    x, y, rot = 0.0, 0.0, 0.0
    if at and len(at) >= 3:
        x, y = float(at[1]), float(at[2])
        if len(at) >= 4:
            rot = float(at[3])
    layer = _find_str(node, "layer", "F.Cu")
    uuid = _find_str(node, "uuid", "")
    ref = ""
    value = ""
    for child in node[1:]:
        if isinstance(child, list) and child[0] == "property" and len(child) >= 3:
            if child[1] == "Reference":
                ref = child[2]
            elif child[1] == "Value":
                value = child[2]
        if isinstance(child, list) and child[0] == "fp_text" and len(child) >= 3:
            if child[1] == "reference":
                ref = child[2]
            elif child[1] == "value":
                value = child[2]
    pads = _extract_pads(node, x, y, rot, nets)
    return Footprint(
        ref=ref, value=value, lib_id=lib_id,
        x=x, y=y, rotation=rot, layer=layer,
        pads=pads, uuid=uuid,
    )


def _extract_pads(
    fp_node: list, fp_x: float, fp_y: float, fp_rot: float,
    nets: dict[str, int],
) -> list[Pad]:
    import math
    results: list[Pad] = []
    for child in fp_node[1:]:
        if not isinstance(child, list) or child[0] != "pad":
            continue
        if len(child) < 4:
            continue
        number = str(child[1])
        pad_type = str(child[2])
        shape = str(child[3])
        at = _find_list(child, "at")
        local_x, local_y = 0.0, 0.0
        if at and len(at) >= 3:
            local_x, local_y = float(at[1]), float(at[2])
        rad = math.radians(fp_rot)
        cos_r, sin_r = math.cos(rad), math.sin(rad)
        abs_x = fp_x + local_x * cos_r - local_y * sin_r
        abs_y = fp_y + local_x * sin_r + local_y * cos_r
        size = _find_list(child, "size")
        w, h = 1.0, 1.0
        if size and len(size) >= 3:
            w, h = float(size[1]), float(size[2])
        drill = _find_list(child, "drill")
        drill_size = 0.0
        if drill and len(drill) >= 2:
            try:
                drill_size = float(drill[1])
            except ValueError:
                pass
        net_node = _find_list(child, "net")
        net_id = 0
        net_name = ""
        if net_node and len(net_node) >= 3:
            net_id = int(net_node[1])
            net_name = str(net_node[2])
        layers_node = _find_list(child, "layers")
        layers = []
        if layers_node:
            layers = [str(layer_name) for layer_name in layers_node[1:]]
        results.append(Pad(
            number=number, pad_type=pad_type, shape=shape,
            x=abs_x, y=abs_y, width=w, height=h,
            drill=drill_size, net_name=net_name, net_id=net_id,
            layers=layers,
        ))
    return results


def _extract_edges(tree: list) -> list[EdgeSegment]:
    edges: list[EdgeSegment] = []
    for node in tree[1:]:
        if not isinstance(node, list):
            continue
        if node[0] in ("gr_line", "fp_line"):
            layer = _find_str(node, "layer", "")
            if "Edge.Cuts" not in layer:
                continue
            start = _find_list(node, "start")
            end = _find_list(node, "end")
            if start and end and len(start) >= 3 and len(end) >= 3:
                edges.append(EdgeSegment(
                    x1=float(start[1]), y1=float(start[2]),
                    x2=float(end[1]), y2=float(end[2]),
                ))
        elif node[0] == "gr_rect":
            layer = _find_str(node, "layer", "")
            if "Edge.Cuts" not in layer:
                continue
            start = _find_list(node, "start")
            end = _find_list(node, "end")
            if start and end and len(start) >= 3 and len(end) >= 3:
                x1, y1 = float(start[1]), float(start[2])
                x2, y2 = float(end[1]), float(end[2])
                edges.append(EdgeSegment(x1=x1, y1=y1, x2=x2, y2=y1))
                edges.append(EdgeSegment(x1=x2, y1=y1, x2=x2, y2=y2))
                edges.append(EdgeSegment(x1=x2, y1=y2, x2=x1, y2=y2))
                edges.append(EdgeSegment(x1=x1, y1=y2, x2=x1, y2=y1))
        elif node[0] == "gr_circle":
            layer = _find_str(node, "layer", "")
            if "Edge.Cuts" not in layer:
                continue
            center = _find_list(node, "center")
            end = _find_list(node, "end")
            if center and end and len(center) >= 3 and len(end) >= 3:
                import math
                cx, cy = float(center[1]), float(center[2])
                ex, ey = float(end[1]), float(end[2])
                r = math.hypot(ex - cx, ey - cy)
                n_segments = 32
                for i in range(n_segments):
                    a1 = 2 * math.pi * i / n_segments
                    a2 = 2 * math.pi * (i + 1) / n_segments
                    edges.append(EdgeSegment(
                        x1=cx + r * math.cos(a1), y1=cy + r * math.sin(a1),
                        x2=cx + r * math.cos(a2), y2=cy + r * math.sin(a2),
                    ))
    return edges


def _find_str(tree: list, key: str, default: str = "") -> str:
    for node in tree[1:]:
        if isinstance(node, list) and len(node) >= 2 and node[0] == key:
            return str(node[1])
    return default


def _find_list(tree: list, key: str) -> list | None:
    for node in tree[1:]:
        if isinstance(node, list) and node[0] == key:
            return node
    return None
