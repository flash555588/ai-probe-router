"""Concrete module graph models produced after module selection."""

from __future__ import annotations

from dataclasses import dataclass, field

from .board import BoundingBox
from .module import AiHint, ComponentSpec


@dataclass
class ModuleInstance:
    instance_id: str
    name: str
    module_type: str
    required: bool
    version: str = ""
    requested_version: str = ""
    selected_definition: str = ""
    selected_definition_version: str = ""
    selected_implementation: str = ""
    selected_implementation_version: str = ""
    implementation_constraints: dict = field(default_factory=dict)
    components: list[ComponentSpec] = field(default_factory=list)
    generated_nets: list[str] = field(default_factory=list)
    target_nets: list[str] = field(default_factory=list)
    required_buses: list[str] = field(default_factory=list)
    voltage_domains: list[str] = field(default_factory=list)
    rails: list[str] = field(default_factory=list)
    area_mm2: float = 0.0
    budget_area_mm2: float = 0.0
    review_required: bool = False
    refdes_pools: dict[str, list[str]] = field(default_factory=dict)
    preferred_region: str = ""
    ai_hints: list[AiHint] = field(default_factory=list)
    region: BoundingBox | None = None


@dataclass
class ModuleDependency:
    source_id: str
    target_id: str
    reason: str
    directed: bool = True


@dataclass
class BusGroup:
    bus_type: str
    modules: list[str] = field(default_factory=list)
    addresses: dict[str, str] = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)
    pullup_required: bool = False
    pullup_covered: bool = False


@dataclass
class PowerDomainUsage:
    domain_name: str
    modules: list[str] = field(default_factory=list)
    current_ma: float = 0.0
    max_current_ma: float = 0.0
    warnings: list[str] = field(default_factory=list)


@dataclass
class ModuleGraph:
    instances: list[ModuleInstance] = field(default_factory=list)
    dependencies: list[ModuleDependency] = field(default_factory=list)
    bus_groups: list[BusGroup] = field(default_factory=list)
    power_domains: list[PowerDomainUsage] = field(default_factory=list)

    def by_name(self) -> dict[str, ModuleInstance]:
        return {instance.name: instance for instance in self.instances}

    def by_id(self) -> dict[str, ModuleInstance]:
        return {instance.instance_id: instance for instance in self.instances}


@dataclass
class ModuleGraphResult:
    graph: ModuleGraph = field(default_factory=ModuleGraph)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ignored_hints: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors
