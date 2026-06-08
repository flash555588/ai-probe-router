"""Resource allocator for multi-module system planning.

Orchestrates bus, power-domain, and connector-pin allocation
while preserving deterministic safety and backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .bus_allocator import BusAllocationResult, allocate_buses
from .power_domain_solver import PowerAllocationResult, allocate_power

if TYPE_CHECKING:
    from ..config import ProjectConfig
    from ..models.module import SelectedModule


@dataclass
class ResourceAllocationResult:
    ok: bool = True
    bus_result: BusAllocationResult = field(default_factory=BusAllocationResult)
    power_result: PowerAllocationResult = field(default_factory=PowerAllocationResult)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return bool(self.errors)


def allocate_resources(
    modules: list[SelectedModule],
    cfg: ProjectConfig,
) -> ResourceAllocationResult:
    """Allocate buses, power domains, and connector pins for selected modules."""
    if not cfg.resource_allocator.enable:
        return ResourceAllocationResult(
            ok=True,
            warnings=["RESOURCE_ALLOCATOR_DISABLED"],
        )

    bus_result = allocate_buses(
        modules,
        strategy=cfg.resource_allocator.bus_allocation_strategy,
    )
    power_result = allocate_power(
        modules,
        cfg.hardware_platform.target_voltage_domains,
        strategy=cfg.resource_allocator.power_allocation_strategy,
    )

    errors: list[str] = []
    warnings: list[str] = []

    if bus_result.conflicts:
        errors.append("BUS_ADDRESS_CONFLICT_UNRESOLVED")
        for c in bus_result.conflicts:
            errors.append(f"  bus={c.bus_type} addr={c.address} modules={c.modules}")
    if bus_result.near_limit:
        warnings.append("BUS_ALLOCATION_NEAR_LIMIT")

    if power_result.overload_domains:
        errors.append("POWER_DOMAIN_OVERLOAD")
        for d in power_result.overload_domains:
            errors.append(f"  domain={d.domain_name} budget={d.budget_ma}mA "
                         f"requested={d.requested_ma}mA")
    if power_result.near_limit_domains:
        warnings.append("POWER_DOMAIN_NEAR_LIMIT")
        for d in power_result.near_limit_domains:
            warnings.append(f"  domain={d.domain_name} "
                           f"headroom={d.headroom_percent:.0f}%")

    if cfg.resource_allocator.allow_partial_allocation:
        ok = bool(errors) is False or bool(bus_result.assignments)
    else:
        ok = not errors

    return ResourceAllocationResult(
        ok=ok,
        bus_result=bus_result,
        power_result=power_result,
        warnings=warnings,
        errors=errors,
    )
