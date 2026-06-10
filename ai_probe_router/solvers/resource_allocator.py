"""Resource allocator for multi-module system planning.

Orchestrates bus, power-domain, and connector-pin allocation
while preserving deterministic safety and backward compatibility.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..models.readiness_codes import ReadinessCode
from .bus_allocator import BusAllocationResult, allocate_buses
from .connector_allocator import ConnectorAllocationResult
from .power_domain_solver import PowerAllocationResult, allocate_power

if TYPE_CHECKING:
    from ..config import ProjectConfig
    from ..models.module import SelectedModule

_logger = logging.getLogger(__name__)


@dataclass
class ResourceAllocationResult:
    ok: bool = True
    bus_result: BusAllocationResult = field(default_factory=BusAllocationResult)
    power_result: PowerAllocationResult = field(default_factory=PowerAllocationResult)
    connector_result: ConnectorAllocationResult | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    simulated: bool = False

    @property
    def blocked(self) -> bool:
        return bool(self.errors)

def allocate_resources(
    modules: list[SelectedModule],
    cfg: ProjectConfig,
    *,
    simulate: bool = False,
) -> ResourceAllocationResult:
    """Allocate buses, power domains, and connector pins for selected modules.

    Parameters
    ----------
    simulate:
        If True, perform a dry-run allocation without writing any files.
        The result still contains all warnings and errors.
    """
    ra_cfg = cfg.resource_allocator
    if not ra_cfg.enable:
        _logger.info("Resource allocator disabled; skipping allocation.")
        return ResourceAllocationResult(
            ok=True,
            warnings=[ReadinessCode.RESOURCE_ALLOCATOR_DISABLED],
            simulated=simulate,
        )

    _logger.info(
        "Starting resource allocation for %d modules (simulate=%s)",
        len(modules),
        simulate,
    )

    bus_result = allocate_buses(
        modules,
        strategy=ra_cfg.bus_allocation_strategy,
    )
    _logger.info(
        "Bus allocation: %d assignments, %d conflicts",
        len(bus_result.assignments),
        len(bus_result.conflicts),
    )

    power_result = allocate_power(
        modules,
        cfg.hardware_platform.target_voltage_domains,
        strategy=ra_cfg.power_allocation_strategy,
        near_limit_threshold=ra_cfg.near_limit_threshold,
        overload_block=ra_cfg.overload_block,
    )
    _logger.info(
        "Power allocation: %d domains, %d overloads, %d near-limit",
        len(power_result.domains),
        len(power_result.overload_domains),
        len(power_result.near_limit_domains),
    )

    errors: list[str] = []
    warnings: list[str] = []

    if bus_result.conflicts:
        errors.append(ReadinessCode.BUS_ADDRESS_CONFLICT_UNRESOLVED)
        for c in bus_result.conflicts:
            errors.append(f"  bus={c.bus_type} addr={c.address} modules={c.modules}")
    if bus_result.near_limit:
        warnings.append(ReadinessCode.BUS_ALLOCATION_NEAR_LIMIT)

    if power_result.overload_domains:
        errors.append(ReadinessCode.POWER_DOMAIN_OVERLOAD)
        for d in power_result.overload_domains:
            errors.append(
                f"  domain={d.domain_name} budget={d.budget_ma}mA "
                f"requested={d.requested_ma}mA"
            )
    if power_result.near_limit_domains:
        warnings.append(ReadinessCode.POWER_DOMAIN_NEAR_LIMIT)
        for d in power_result.near_limit_domains:
            warnings.append(
                f"  domain={d.domain_name} "
                f"headroom={d.headroom_percent:.0f}%"
            )

    if ra_cfg.allow_partial_allocation:
        ok = bool(errors) is False or bool(bus_result.assignments)
    else:
        ok = not errors

    if not ok:
        _logger.warning("Resource allocation blocked: %d errors", len(errors))
    else:
        _logger.info("Resource allocation completed successfully.")

    return ResourceAllocationResult(
        ok=ok,
        bus_result=bus_result,
        power_result=power_result,
        warnings=warnings,
        errors=errors,
        simulated=simulate,
    )
