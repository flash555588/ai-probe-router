"""Typed intermediate circuit specification for schema-v2 configs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..config import ProjectConfig


@dataclass(frozen=True)
class ComponentSpec:
    name: str
    module_type: str
    required: bool = True
    target_nets: tuple[str, ...] = ()
    rails: tuple[str, ...] = ()
    allowed_interfaces: tuple[str, ...] = ()
    telemetry_bus: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    require_esd: bool = False


@dataclass(frozen=True)
class NetSpec:
    name: str
    source: str = ""


@dataclass(frozen=True)
class PowerDomainSpec:
    name: str
    voltage: float = 0.0
    max_current_ma: float = 0.0


@dataclass(frozen=True)
class CircuitSpec:
    schema_version: int
    components: tuple[ComponentSpec, ...] = ()
    nets: tuple[NetSpec, ...] = ()
    power_domains: tuple[PowerDomainSpec, ...] = ()
    protection_roles: tuple[str, ...] = ()
    impedance_rules: tuple[str, ...] = ()

    @property
    def net_names(self) -> set[str]:
        return {net.name for net in self.nets if net.name}

    @property
    def rail_names(self) -> set[str]:
        return {domain.name for domain in self.power_domains if domain.name}


def build_circuit_spec(
    cfg: ProjectConfig,
    schematic_net_names: set[str] | None = None,
) -> CircuitSpec:
    """Build a typed intermediate spec from loaded project config."""
    nets: dict[str, NetSpec] = {}
    for name in schematic_net_names or set():
        if name:
            nets[name] = NetSpec(name=name, source="schematic")
    for req in cfg.nets_to_expose:
        if req.net_name and req.net_name not in nets:
            nets[req.net_name] = NetSpec(name=req.net_name, source="probe")
        if req.pair_net_name and req.pair_net_name not in nets:
            nets[req.pair_net_name] = NetSpec(name=req.pair_net_name, source="probe_pair")

    components: list[ComponentSpec] = []
    for module in cfg.functional_modules:
        components.append(
            ComponentSpec(
                name=module.name,
                module_type=module.type,
                required=module.required,
                target_nets=tuple(module.target_nets),
                rails=tuple(module.rails or module.voltage_domains),
                allowed_interfaces=tuple(module.allowed_interfaces),
                telemetry_bus=module.telemetry_bus,
                params=_module_params(module.params),
                require_esd=module.require_esd,
            )
        )
        for net in module.target_nets:
            if net and net not in nets:
                nets[net] = NetSpec(name=net, source=f"module:{module.name}")

    return CircuitSpec(
        schema_version=cfg.schema_version,
        components=tuple(components),
        nets=tuple(sorted(nets.values(), key=lambda n: n.name)),
        power_domains=tuple(
            PowerDomainSpec(
                name=domain.name,
                voltage=domain.voltage,
                max_current_ma=domain.max_current_ma,
            )
            for domain in cfg.hardware_platform.target_voltage_domains
        ),
        protection_roles=tuple(sorted(cfg.protection.rules)) if cfg.protection.enabled else (),
        impedance_rules=tuple(sorted(cfg.impedance_control.rules)),
    )


def _module_params(raw: dict[str, Any]) -> dict[str, Any]:
    params = dict(raw)
    nested = params.pop("params", {})
    if isinstance(nested, dict):
        params.update(nested)
    return params
