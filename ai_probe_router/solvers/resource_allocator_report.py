"""Resource allocation report formatting."""

from __future__ import annotations

import json
from pathlib import Path

from .resource_allocator import ResourceAllocationResult


def generate_resource_allocation_json(result: ResourceAllocationResult) -> str:
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
