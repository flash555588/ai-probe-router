"""KiCad schematic healthcheck and repair helpers."""

from __future__ import annotations

import re
import uuid as _uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .sexpr import QuotedStr, SExpr, parse, serialize

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


@dataclass(frozen=True)
class SchematicHealthReport:
    file: str
    balanced_sexpr: bool
    uuid_count: int
    quoted_uuid_count: int
    invalid_uuid_count: int
    schematic_symbol_instances: int
    schematic_symbol_count: int
    has_sheet_instances: bool
    parse_error: str = ""

    @property
    def ok(self) -> bool:
        return (
            self.balanced_sexpr
            and self.invalid_uuid_count == 0
            and self.quoted_uuid_count == 0
            and self.schematic_symbol_instances == self.schematic_symbol_count
            and self.has_sheet_instances
        )

    def to_lines(self) -> list[str]:
        return [
            f"file: {self.file}",
            f"balanced_sexpr: {self.balanced_sexpr}",
            f"uuid_count: {self.uuid_count}",
            f"quoted_uuid_count: {self.quoted_uuid_count}",
            f"invalid_uuid_count: {self.invalid_uuid_count}",
            "schematic_symbol_instances: "
            f"{self.schematic_symbol_instances}/{self.schematic_symbol_count}",
            f"has_sheet_instances: {self.has_sheet_instances}",
            f"parse_error: {self.parse_error}" if self.parse_error else "",
        ]


def healthcheck_schematic(path: str | Path) -> SchematicHealthReport:
    path = Path(path)
    try:
        tree = parse(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return SchematicHealthReport(
            file=str(path),
            balanced_sexpr=False,
            uuid_count=0,
            quoted_uuid_count=0,
            invalid_uuid_count=0,
            schematic_symbol_instances=0,
            schematic_symbol_count=0,
            has_sheet_instances=False,
            parse_error=str(exc),
        )
    if not isinstance(tree, list) or not tree or tree[0] != "kicad_sch":
        return SchematicHealthReport(
            file=str(path),
            balanced_sexpr=False,
            uuid_count=0,
            quoted_uuid_count=0,
            invalid_uuid_count=0,
            schematic_symbol_instances=0,
            schematic_symbol_count=0,
            has_sheet_instances=False,
            parse_error="Not a KiCad schematic",
        )
    return inspect_schematic_health(tree, file=str(path))


def inspect_schematic_health(tree: list, file: str = "<memory>") -> SchematicHealthReport:
    uuid_values = list(_iter_uuid_values(tree))
    schematic_symbols = [
        node
        for node in tree[1:]
        if isinstance(node, list) and node and node[0] == "symbol" and _find_child(node, "lib_id")
    ]
    return SchematicHealthReport(
        file=file,
        balanced_sexpr=True,
        uuid_count=len(uuid_values),
        quoted_uuid_count=sum(1 for value in uuid_values if isinstance(value, QuotedStr)),
        invalid_uuid_count=sum(1 for value in uuid_values if not _UUID_RE.match(str(value))),
        schematic_symbol_instances=sum(
            1 for node in schematic_symbols if _find_child(node, "instances")
        ),
        schematic_symbol_count=len(schematic_symbols),
        has_sheet_instances=_find_child(tree, "sheet_instances") is not None,
    )


def repair_schematic_tree(tree: list) -> list:
    """Repair common KiCad schematic metadata issues in-place and return tree."""
    if not isinstance(tree, list) or not tree or tree[0] != "kicad_sch":
        raise ValueError("Not a KiCad schematic tree")
    _set_compact_child(tree, "generator", "ai-probe-router")
    _set_compact_child(tree, "generator_version", "1.0.0")
    _repair_uuid_nodes(tree)
    for node in tree[1:]:
        if isinstance(node, list) and node and node[0] == "symbol" and _find_child(node, "lib_id"):
            _ensure_symbol_instances(node)
    _ensure_sheet_instances(tree)
    return tree


def repair_schematic_file(input_path: str | Path, output_path: str | Path | None = None) -> Path:
    input_path = Path(input_path)
    output = Path(output_path) if output_path is not None else input_path
    tree = parse(input_path.read_text(encoding="utf-8"))
    if not isinstance(tree, list):
        raise ValueError(f"Not a KiCad schematic: {input_path}")
    repair_schematic_tree(tree)
    output.write_text(serialize(tree) + "\n", encoding="utf-8")
    return output


def _iter_uuid_values(expr: SExpr) -> Iterable[str]:
    if not isinstance(expr, list):
        return
    if len(expr) >= 2 and expr[0] == "uuid" and isinstance(expr[1], str):
        yield expr[1]
    for child in expr:
        if isinstance(child, list):
            yield from _iter_uuid_values(child)


def _repair_uuid_nodes(expr: SExpr) -> None:
    if not isinstance(expr, list):
        return
    if len(expr) >= 2 and expr[0] == "uuid" and isinstance(expr[1], str):
        expr[1] = _normalize_uuid(expr[1])
    for child in expr:
        if isinstance(child, list):
            _repair_uuid_nodes(child)


def _normalize_uuid(value: str) -> str:
    if isinstance(value, QuotedStr) or not _UUID_RE.match(str(value)):
        return str(_uuid.uuid4())
    return str(value)


def _ensure_symbol_instances(symbol_node: list) -> None:
    if _find_child(symbol_node, "instances") is not None:
        return
    ref = _property_value(symbol_node, "Reference", "U?")
    symbol_node.append([
        "instances",
        ["project", "",
         ["path", "/", ["reference", str(ref)], ["unit", "1"]]],
    ])


def _ensure_sheet_instances(tree: list) -> None:
    if _find_child(tree, "sheet_instances") is None:
        tree.append([
            "sheet_instances",
            ["path", QuotedStr("/"), ["page", QuotedStr("1")]],
        ])


def _set_compact_child(tree: list, key: str, value: str) -> None:
    child = _find_child(tree, key)
    if child is None:
        insert_at = _root_insert_index(tree, key)
        tree.insert(insert_at, [key, value])
    elif len(child) >= 2:
        child[1] = value
    else:
        child.append(value)


def _root_insert_index(tree: list, key: str) -> int:
    order = ["version", "generator", "generator_version", "uuid", "paper"]
    key_index = order.index(key) if key in order else len(order)
    insert_at = 1
    for index, node in enumerate(tree[1:], start=1):
        if not isinstance(node, list) or not node:
            continue
        if node[0] in order and order.index(node[0]) <= key_index:
            insert_at = index + 1
    return insert_at


def _property_value(symbol_node: list, name: str, default: str) -> str:
    for child in symbol_node[1:]:
        if (
            isinstance(child, list)
            and len(child) >= 3
            and child[0] == "property"
            and child[1] == name
        ):
            return str(child[2])
    return default


def _find_child(tree: list, key: str) -> list | None:
    for child in tree[1:]:
        if isinstance(child, list) and child and child[0] == key:
            return child
    return None
