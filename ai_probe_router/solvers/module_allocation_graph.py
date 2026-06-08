"""Module allocation graph: ties resource-allocation results to the module graph.

This is a thin deterministic wrapper that annotates a ModuleGraph with
allocated buses, power domains, and connector-pin reservations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .bus_allocator import BusAllocationResult
from .power_domain_solver import PowerAllocationResult
from .resource_allocator import ResourceAllocationResult


@dataclass
class AllocatedModuleGraph:
    """Module graph annotated with resource-allocation decisions."""

    bus_assignments: list[dict] = field(default_factory=list)
    power_assignments: list[dict] = field(default_factory=list)
    connector_reservations: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def build_allocated_module_graph(
    allocation_result: ResourceAllocationResult,
) -> AllocatedModuleGraph:
    """Convert a ResourceAllocationResult into an annotated graph."""
    graph = AllocatedModuleGraph()

    bus: BusAllocationResult = allocation_result.bus_result
    for a in bus.assignments:
        graph.bus_assignments.append(
            {
                "bus_type": a.bus_type,
                "bus_id": a.bus_id,
                "module": a.module_name,
                "instance_id": a.instance_id,
                "address": a.address,
            }
        )
    for c in bus.conflicts:
        graph.errors.append(
            f"BUS_CONFLICT {c.bus_type} addr={c.address} modules={c.modules}"
        )
    if bus.near_limit:
        graph.warnings.append("BUS_ALLOCATION_NEAR_LIMIT")

    power: PowerAllocationResult = allocation_result.power_result
    for d in power.domains:
        graph.power_assignments.append(
            {
                "domain": d.domain_name,
                "voltage": d.voltage,
                "budget_ma": d.budget_ma,
                "requested_ma": d.requested_ma,
                "headroom_percent": round(d.headroom_percent, 1),
            }
        )
    for o in power.overload_domains:
        graph.errors.append(
            f"POWER_OVERLOAD domain={o.domain_name} "
            f"budget={o.budget_ma}mA requested={o.requested_ma}mA"
        )
    for n in power.near_limit_domains:
        graph.warnings.append(
            f"POWER_NEAR_LIMIT domain={n.domain_name} "
            f"headroom={n.headroom_percent:.0f}%"
        )

    # Connector reservations are computed later from pin mapping
    # This placeholder keeps the API stable for PR6.
    graph.connector_reservations = []

    return graph
