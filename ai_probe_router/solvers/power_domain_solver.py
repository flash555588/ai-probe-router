"""Power domain solver: sums module currents and checks rail budgets."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models.module import SelectedModule
from ..models.power_domain import PowerDomain


@dataclass
class PowerDomainStatus:
    domain_name: str
    voltage: float
    budget_ma: float
    requested_ma: float
    headroom_percent: float


@dataclass
class PowerAllocationResult:
    domains: list[PowerDomainStatus] = field(default_factory=list)
    overload_domains: list[PowerDomainStatus] = field(default_factory=list)
    near_limit_domains: list[PowerDomainStatus] = field(default_factory=list)


def allocate_power(
    modules: list[SelectedModule],
    platform_domains: list[PowerDomain],
    strategy: str = "max_headroom",
    *,
    near_limit_threshold: float = 0.8,
    overload_block: bool = True,
) -> PowerAllocationResult:
    """Sum module currents per voltage domain and compare against budget.

    Parameters
    ----------
    near_limit_threshold:
        Fraction of budget used before a domain is flagged as near-limit.
    overload_block:
        If True, overloads are reported in ``overload_domains``.
        If False, they are still reported but not treated as fatal.
    """
    result = PowerAllocationResult()
    budget_by_voltage: dict[float, float] = {}
    for pd in platform_domains:
        budget_by_voltage[pd.voltage] = pd.max_current_ma

    # Gather current draws from module implementations
    draw_by_voltage: dict[float, float] = {}
    for sel in modules:
        impl = sel.implementation
        if not impl.components:
            continue
        for comp in impl.components:
            voltage = _infer_component_voltage(comp)
            current = _infer_component_current(comp)
            draw_by_voltage[voltage] = draw_by_voltage.get(voltage, 0.0) + current

    # Map to named domains
    for pd in platform_domains:
        requested = draw_by_voltage.get(pd.voltage, 0.0)
        budget = pd.max_current_ma
        headroom = (
            round((budget - requested) / budget * 100, 1) if budget > 0 else 0.0
        )
        status = PowerDomainStatus(
            domain_name=pd.name,
            voltage=pd.voltage,
            budget_ma=budget,
            requested_ma=requested,
            headroom_percent=headroom,
        )
        result.domains.append(status)
        if budget > 0 and requested > budget:
            result.overload_domains.append(status)
        elif budget > 0 and requested >= budget * near_limit_threshold:
            result.near_limit_domains.append(status)

    return result

def _infer_component_voltage(comp) -> float:
    """Infer nominal voltage from component metadata."""
    # Default to 3.3V when unknown
    chip = getattr(comp, "chip", "")
    if chip and "5v" in str(chip).lower():
        return 5.0
    if chip and "1v8" in str(chip).lower():
        return 1.8
    return 3.3


def _infer_component_current(comp) -> float:
    """Infer current draw from component metadata."""
    # Use explicit current if provided, else heuristic by type
    current = getattr(comp, "current_ma", 0.0)
    if current:
        return float(current)
    comp_type = getattr(comp, "type", "").lower()
    if comp_type in ("mcu", "wifi_mcu", "processor"):
        return 100.0
    if comp_type in ("motor_driver", "power_reg"):
        return 500.0
    if comp_type in ("led", "testpad"):
        return 5.0
    if comp_type in ("esd_array", "matching_network", "crystal"):
        return 1.0
    if comp_type in ("eeprom", "i2c_eeprom"):
        return 2.0
    return 10.0
