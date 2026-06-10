"""Resource allocation report formatting."""

from __future__ import annotations

import json
from pathlib import Path

from .module_allocation_graph import build_allocated_module_graph
from .resource_allocator import ResourceAllocationResult
from .resource_optimizer import (
    generate_resource_optimization_report,
    write_resource_optimization_report,
)


def _connector_result_data(result: ResourceAllocationResult) -> dict | None:
    connector = result.connector_result
    if connector is None:
        return None
    return {
        "strategy": connector.strategy,
        "connector_type": connector.connector_type,
        "rows": connector.rows,
        "pins_per_row": connector.pins_per_row,
        "used_pins": connector.used_pins,
        "free_pins": connector.free_pins,
        "utilization_percent": connector.utilization_percent,
        "spread_span": connector.spread_span,
        "near_limit": connector.near_limit,
        "conflicts": [
            {
                "pin_index": c.pin_index,
                "pin_name": c.pin_name,
                "nets": c.nets,
            }
            for c in connector.conflicts
        ],
        "warnings": connector.warnings,
        "errors": connector.errors,
    }


def generate_resource_allocation_json(result: ResourceAllocationResult) -> str:
    graph = build_allocated_module_graph(result)
    data = {
        "schema_version": 1,
        "ok": result.ok,
        "warnings": result.warnings,
        "errors": result.errors,
        "bus_result": {
            "assignments": [
                {
                    "bus_type": a.bus_type,
                    "bus_id": a.bus_id,
                    "module_name": a.module_name,
                    "instance_id": a.instance_id,
                    "address": a.address,
                }
                for a in result.bus_result.assignments
            ],
            "conflicts": [
                {
                    "bus_type": c.bus_type,
                    "address": c.address,
                    "modules": c.modules,
                }
                for c in result.bus_result.conflicts
            ],
            "near_limit": result.bus_result.near_limit,
        },
        "power_result": {
            "domains": [
                {
                    "domain_name": d.domain_name,
                    "voltage": d.voltage,
                    "budget_ma": d.budget_ma,
                    "requested_ma": d.requested_ma,
                    "headroom_percent": d.headroom_percent,
                }
                for d in result.power_result.domains
            ],
            "overload_domains": [
                {
                    "domain_name": d.domain_name,
                    "voltage": d.voltage,
                    "budget_ma": d.budget_ma,
                    "requested_ma": d.requested_ma,
                    "headroom_percent": d.headroom_percent,
                }
                for d in result.power_result.overload_domains
            ],
            "near_limit_domains": [
                {
                    "domain_name": d.domain_name,
                    "voltage": d.voltage,
                    "budget_ma": d.budget_ma,
                    "requested_ma": d.requested_ma,
                    "headroom_percent": d.headroom_percent,
                }
                for d in result.power_result.near_limit_domains
            ],
        },
        "connector_result": _connector_result_data(result),
        "allocation_graph": {
            "ok": graph.ok,
            "bus_assignments": graph.bus_assignments,
            "power_assignments": graph.power_assignments,
            "connector_reservations": graph.connector_reservations,
            "warnings": graph.warnings,
            "errors": graph.errors,
        },
    }
    return json.dumps(data, indent=2)


def write_resource_allocation_report(
    result: ResourceAllocationResult,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "resource_allocation_report.json"
    json_path.write_text(
        generate_resource_allocation_json(result), encoding="utf-8"
    )
    write_resource_optimization_report(
        generate_resource_optimization_report(result),
        output_dir,
    )
