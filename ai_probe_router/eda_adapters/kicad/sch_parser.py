"""Parse KiCad .kicad_sch files into Schematic model."""

from __future__ import annotations

from pathlib import Path

from ...models.board import Schematic
from ...models.component import Component, Pin
from ..kicad.sexpr import parse


def parse_schematic(path: str | Path) -> Schematic:
    text = Path(path).read_text(encoding="utf-8")
    tree = parse(text)
    if not isinstance(tree, list) or tree[0] != "kicad_sch":
        raise ValueError(f"Not a KiCad schematic: {path}")
    components = _extract_components(tree)
    labels = _extract_labels(tree)
    wires = _extract_wires(tree)
    return Schematic(components=components, labels=labels, wires=wires, raw=tree)


def _extract_components(tree: list) -> list[Component]:
    results: list[Component] = []
    for node in tree[1:]:
        if not isinstance(node, list) or node[0] != "symbol":
            continue
        if _find_str(node, "lib_id", "") == "":
            continue
        comp = _parse_component(node)
        if comp:
            results.append(comp)
    return results


def _parse_component(node: list) -> Component | None:
    lib_id = _find_str(node, "lib_id", "")
    is_power = lib_id.startswith("power:")
    at = _find_list(node, "at")
    x, y, rot = 0.0, 0.0, 0.0
    if at and len(at) >= 3:
        x, y = float(at[1]), float(at[2])
        if len(at) >= 4:
            rot = float(at[3])
    uuid = _find_str(node, "uuid", "")
    dnp = _find_str(node, "dnp", "no") == "yes"
    props = {}
    ref = ""
    value = ""
    for child in node[1:]:
        if isinstance(child, list) and child[0] == "property" and len(child) >= 3:
            props[child[1]] = child[2]
            if child[1] == "Reference":
                ref = child[2]
            elif child[1] == "Value":
                value = child[2]
    pins = []
    for child in node[1:]:
        if isinstance(child, list) and child[0] == "pin":
            pins.append(Pin(number=child[1] if len(child) > 1 else ""))
    return Component(
        ref=ref, value=value, lib_id=lib_id,
        x=x, y=y, rotation=rot,
        pins=pins, properties=props, uuid=uuid,
        dnp=dnp, is_power_symbol=is_power,
    )


def _extract_labels(tree: list) -> list[dict]:
    results = []
    for node in tree[1:]:
        if not isinstance(node, list):
            continue
        if node[0] in ("label", "global_label", "hierarchical_label"):
            name = node[1] if len(node) > 1 and isinstance(node[1], str) else ""
            at = _find_list(node, "at")
            x, y = 0.0, 0.0
            if at and len(at) >= 3:
                x, y = float(at[1]), float(at[2])
            results.append({
                "type": node[0], "name": name,
                "x": x, "y": y,
                "uuid": _find_str(node, "uuid", ""),
            })
    return results


def _extract_wires(tree: list) -> list[dict]:
    results = []
    for node in tree[1:]:
        if isinstance(node, list) and node[0] == "wire":
            pts = _find_list(node, "pts")
            if pts:
                points = []
                for p in pts[1:]:
                    if isinstance(p, list) and p[0] == "xy" and len(p) >= 3:
                        points.append((float(p[1]), float(p[2])))
                results.append({"points": points})
    return results


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
