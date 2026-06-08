"""Generate schematic scaffolding for module instances."""

from __future__ import annotations

import uuid as _uuid
from dataclasses import dataclass, field
from pathlib import Path

from ..eda_adapters.kicad.sch_writer import add_module_sheet_symbol
from ..eda_adapters.kicad.sexpr import serialize
from ..models.board import Schematic
from ..models.module_graph import ModuleGraph, ModuleInstance


@dataclass
class GeneratedModuleSheet:
    module_id: str
    module_name: str
    sheet_file: str
    absolute_path: str
    run_id: str = ""
    pins: list[str] = field(default_factory=list)


@dataclass
class ModuleInstantiationResult:
    run_id: str = ""
    sheets: list[GeneratedModuleSheet] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""
    warnings: list[str] = field(default_factory=list)


def instantiate_module_sheets(
    sch: Schematic | None,
    graph: ModuleGraph,
    output_dir: str | Path,
    run_id: str = "",
) -> ModuleInstantiationResult:
    result = ModuleInstantiationResult(run_id=run_id)
    if sch is None:
        result.skipped = True
        result.skip_reason = "no_schematic"
        return result

    generated_dir = Path(output_dir) / "generated_modules"
    generated_dir.mkdir(parents=True, exist_ok=True)

    for index, instance in enumerate(graph.instances):
        if _has_existing_sheet(sch, instance.instance_id):
            result.warnings.append(f"{instance.instance_id} sheet already exists; skipped")
            continue
        file_name = f"{instance.instance_id}_{_slug(instance.name)}.kicad_sch"
        relative_file = f"generated_modules/{file_name}"
        absolute_path = generated_dir / file_name
        pins = _sheet_pins(instance)
        _write_child_sheet(absolute_path, instance, pins, run_id)
        x = 25.0 + (index % 3) * 45.0
        y = 25.0 + (index // 3) * 30.0
        add_module_sheet_symbol(sch, instance, relative_file, x, y, run_id=run_id)
        result.sheets.append(
            GeneratedModuleSheet(
                module_id=instance.instance_id,
                module_name=instance.name,
                sheet_file=relative_file,
                absolute_path=str(absolute_path),
                run_id=run_id,
                pins=pins,
            )
        )
    return result


def _write_child_sheet(
    path: Path,
    instance: ModuleInstance,
    pins: list[str],
    run_id: str,
) -> None:
    raw: list = [
        "kicad_sch",
        ["version", "20231120"],
        ["generator", "ai-probe-router"],
        ["uuid", str(_uuid.uuid4())],
        ["paper", "A4"],
        ["lib_symbols"],
        ["text", f"Generated module sheet: {instance.instance_id} {instance.name}",
         ["at", "20", "15", "0"],
         ["effects", ["font", ["size", "1.27", "1.27"]]]],
        ["text", f"Implementation: {instance.selected_implementation}",
         ["at", "20", "20", "0"],
         ["effects", ["font", ["size", "1.27", "1.27"]]]],
    ]
    for index, pin in enumerate(pins):
        raw.append([
            "hierarchical_label", pin,
            ["shape", "input"],
            ["at", "20", str(30 + index * 5.08), "0"],
            ["effects", ["font", ["size", "1.27", "1.27"]]],
            ["uuid", str(_uuid.uuid4())],
        ])
    raw.append([
        "text", "APR_GENERATED=yes",
        ["at", "20", str(35 + len(pins) * 5.08), "0"],
        ["effects", ["font", ["size", "1.0", "1.0"]]],
    ])
    if run_id:
        raw.append([
            "text", f"APR_RUN_ID={run_id}",
            ["at", "20", str(40 + len(pins) * 5.08), "0"],
            ["effects", ["font", ["size", "1.0", "1.0"]]],
        ])
    path.write_text(serialize(raw) + "\n", encoding="utf-8")


def _has_existing_sheet(sch: Schematic, module_id: str) -> bool:
    for node in sch.raw:
        if not (isinstance(node, list) and node and node[0] == "sheet"):
            continue
        for child in node[1:]:
            if (
                isinstance(child, list)
                and len(child) >= 3
                and child[0] == "property"
                and child[1] == "APR_MODULE"
                and child[2] == module_id
            ):
                return True
    return False


def _sheet_pins(instance: ModuleInstance) -> list[str]:
    pins = []
    pins.extend(instance.target_nets)
    pins.extend(instance.generated_nets)
    pins.extend(instance.rails)
    pins.extend(instance.voltage_domains)
    result: list[str] = []
    for pin in pins:
        if pin and pin not in result:
            result.append(pin)
    return result


def _slug(value: str) -> str:
    text = "".join(ch if ch.isalnum() else "_" for ch in value.lower())
    return text.strip("_") or "module"
