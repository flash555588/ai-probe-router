"""Build and validate a deterministic module instance graph."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..models.board import Board
from ..models.module import ComponentSpec
from ..models.module_graph import (
    BusGroup,
    ModuleDependency,
    ModuleGraph,
    ModuleGraphResult,
    ModuleInstance,
    PowerDomainUsage,
)
from .module_selector import ModuleSelectionResult

if TYPE_CHECKING:
    from ..config import ProjectConfig


def build_module_graph(
    cfg: "ProjectConfig",
    selection: ModuleSelectionResult,
    board: Board | None = None,
) -> ModuleGraphResult:
    result = ModuleGraphResult()
    graph = result.graph

    for index, selected in enumerate(selection.selected, start=1):
        module = selected.module
        implementation = selected.implementation
        instance_id = f"MOD{index}"
        instance = ModuleInstance(
            instance_id=instance_id,
            name=module.name,
            module_type=module.type,
            required=module.required,
            version=module.version or selected.definition.version,
            requested_version=module.version,
            selected_definition=selected.definition.name,
            selected_definition_version=selected.definition.version,
            selected_implementation=implementation.name,
            selected_implementation_version=implementation.version,
            implementation_constraints=dict(implementation.constraints),
            components=list(implementation.components),
            generated_nets=_generated_nets(instance_id, module.name, module.target_nets),
            target_nets=list(module.target_nets),
            required_buses=_required_buses(module.telemetry_bus, implementation.interfaces),
            voltage_domains=list(module.voltage_domains),
            rails=list(module.rails),
            area_mm2=implementation.area_mm2,
            budget_area_mm2=module.budget_area_mm2,
            review_required=selected.review_required,
            refdes_pools=_refdes_pools(index, implementation.components),
            preferred_region=module.preferred_region,
            ai_hints=list(module.ai_hints),
        )
        graph.instances.append(instance)
        for hint in instance.ai_hints:
            if not hint.supported:
                result.ignored_hints.append(
                    f"{instance.instance_id}/{instance.name}: {hint.ignored_reason}"
                )

    _add_explicit_dependencies(cfg, graph, result)
    _add_resource_dependencies(graph)
    _validate_cycles(graph, result)
    _validate_version_requests(graph, result)
    _validate_voltage_domains(cfg, graph, result)
    _validate_area_budgets(cfg, graph, result)
    _validate_duplicate_target_nets(graph, result)
    _validate_connector_capacity(cfg, graph, result)
    _build_bus_groups(graph, result)
    _build_power_domains(cfg, graph)

    if board is None:
        result.warnings.append("Module graph built without PCB context")

    return result


def _generated_nets(instance_id: str, module_name: str, target_nets: list[str]) -> list[str]:
    slug = _slug(module_name).upper()
    if not target_nets:
        return [f"{instance_id}_{slug}_LOCAL"]
    return [f"{instance_id}_{slug}_{_slug(net).upper()}" for net in target_nets]


def _required_buses(telemetry_bus: str, interfaces: list[str]) -> list[str]:
    buses = []
    if telemetry_bus:
        buses.append(telemetry_bus)
    buses.extend(interfaces)
    return sorted(set(buses))


def _refdes_pools(
    module_index: int,
    components: list[ComponentSpec],
) -> dict[str, list[str]]:
    counters: dict[str, int] = {}
    pools: dict[str, list[str]] = {}
    base = module_index * 100
    for component in components:
        prefix = _refdes_prefix(component.type)
        refs = []
        for _ in range(component.count):
            counters[prefix] = counters.get(prefix, 0) + 1
            refs.append(f"{prefix}{base + counters[prefix]}")
        pools.setdefault(component.type, []).extend(refs)
    return pools


def _refdes_prefix(component_type: str) -> str:
    mapping = {
        "connector": "J",
        "testpad": "TP",
        "gpio_expander": "U",
        "analog_mux": "U",
        "adc": "U",
        "current_monitor": "U",
        "level_shifter": "U",
        "esd_array": "D",
        "tvs_diode": "D",
        "fuse": "F",
        "efuse": "U",
        "sense_resistor": "R",
        "series_resistor": "R",
        "resistor_array": "RN",
        "pullup_resistor": "R",
        "rc_filter": "R",
        "decoupling_capacitor": "C",
    }
    return mapping.get(component_type, "U")


def _add_explicit_dependencies(
    cfg: "ProjectConfig",
    graph: ModuleGraph,
    result: ModuleGraphResult,
) -> None:
    by_name = graph.by_name()
    for module in cfg.functional_modules:
        source = by_name.get(module.name)
        if source is None:
            continue
        for dep_name in module.depends_on:
            target = by_name.get(dep_name)
            if target is None:
                message = (
                    f"{source.instance_id}/{source.name} depends on missing module "
                    f"'{dep_name}'"
                )
                if source.required:
                    result.errors.append(message)
                else:
                    result.warnings.append(message)
                continue
            graph.dependencies.append(
                ModuleDependency(
                    source_id=source.instance_id,
                    target_id=target.instance_id,
                    reason="depends_on",
                    directed=True,
                )
            )


def _add_resource_dependencies(graph: ModuleGraph) -> None:
    for reason, attr in (
        ("shared_bus", "required_buses"),
        ("shared_rail", "rails"),
        ("shared_target_net", "target_nets"),
    ):
        seen: set[tuple[str, str, str]] = set()
        for i, source in enumerate(graph.instances):
            source_values = set(getattr(source, attr))
            if not source_values:
                continue
            for target in graph.instances[i + 1:]:
                shared = source_values & set(getattr(target, attr))
                for value in sorted(shared):
                    key = (source.instance_id, target.instance_id, value)
                    if key in seen:
                        continue
                    seen.add(key)
                    graph.dependencies.append(
                        ModuleDependency(
                            source_id=source.instance_id,
                            target_id=target.instance_id,
                            reason=f"{reason}:{value}",
                            directed=False,
                        )
                    )


def _validate_cycles(graph: ModuleGraph, result: ModuleGraphResult) -> None:
    edges: dict[str, list[str]] = {}
    for dep in graph.dependencies:
        if not dep.directed:
            continue
        edges.setdefault(dep.source_id, []).append(dep.target_id)

    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> None:
        if node in visited:
            return
        if node in visiting:
            cycle = stack[stack.index(node):] + [node]
            result.errors.append(f"Module dependency cycle: {' -> '.join(cycle)}")
            return
        visiting.add(node)
        stack.append(node)
        for nxt in edges.get(node, []):
            visit(nxt)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for instance in graph.instances:
        visit(instance.instance_id)


def _validate_version_requests(
    graph: ModuleGraph,
    result: ModuleGraphResult,
) -> None:
    for instance in graph.instances:
        requested = instance.requested_version
        library = instance.selected_definition_version
        if not requested or not library or requested == library:
            continue
        message = (
            f"{instance.instance_id}/{instance.name} requested module version "
            f"{requested}, but library definition is {library}"
        )
        if instance.required:
            result.errors.append(message)
        else:
            result.warnings.append(message)


def _validate_voltage_domains(
    cfg: "ProjectConfig",
    graph: ModuleGraph,
    result: ModuleGraphResult,
) -> None:
    available = {
        domain.name
        for domain in cfg.hardware_platform.target_voltage_domains
        if domain.name
    }
    if not available:
        return
    for instance in graph.instances:
        for domain in instance.voltage_domains:
            if domain in available:
                continue
            message = (
                f"{instance.instance_id}/{instance.name} requires missing voltage "
                f"domain '{domain}'"
            )
            if instance.required:
                result.errors.append(message)
            else:
                result.warnings.append(message)


def _validate_area_budgets(
    cfg: "ProjectConfig",
    graph: ModuleGraph,
    result: ModuleGraphResult,
) -> None:
    for instance in graph.instances:
        if instance.budget_area_mm2 <= 0:
            continue
        if instance.area_mm2 <= instance.budget_area_mm2:
            continue
        message = (
            f"{instance.instance_id}/{instance.name} area {instance.area_mm2:.1f}mm^2 "
            f"exceeds budget {instance.budget_area_mm2:.1f}mm^2"
        )
        if instance.required:
            result.errors.append(message)
        else:
            result.warnings.append(message)

    total_budget = cfg.design_goals.max_added_area_mm2
    if total_budget > 0:
        total_area = sum(instance.area_mm2 for instance in graph.instances)
        if total_area > total_budget:
            result.errors.append(
                f"Selected module area {total_area:.1f}mm^2 exceeds global budget "
                f"{total_budget:.1f}mm^2"
            )


def _validate_duplicate_target_nets(
    graph: ModuleGraph,
    result: ModuleGraphResult,
) -> None:
    owners: dict[str, list[ModuleInstance]] = {}
    for instance in graph.instances:
        for net in instance.target_nets:
            owners.setdefault(net, []).append(instance)
    for net, instances in sorted(owners.items()):
        if len(instances) <= 1:
            continue
        names = ", ".join(f"{i.instance_id}/{i.name}" for i in instances)
        message = f"Target net '{net}' reserved by multiple modules: {names}"
        if any(instance.required for instance in instances):
            result.errors.append(message)
        else:
            result.warnings.append(message)


def _validate_connector_capacity(
    cfg: "ProjectConfig",
    graph: ModuleGraph,
    result: ModuleGraphResult,
) -> None:
    if cfg.development_board is None:
        return
    required_nets = {
        net
        for instance in graph.instances
        for net in instance.target_nets
    }
    if len(required_nets) > cfg.development_board.pin_count:
        result.errors.append(
            f"Module target nets require {len(required_nets)} connector pins, "
            f"but {cfg.development_board.name} exposes {cfg.development_board.pin_count}"
        )


def _build_bus_groups(graph: ModuleGraph, result: ModuleGraphResult) -> None:
    groups: dict[str, BusGroup] = {}
    for instance in graph.instances:
        for bus in instance.required_buses:
            group = groups.setdefault(bus, BusGroup(bus_type=bus))
            group.modules.append(instance.instance_id)
            if bus == "i2c":
                group.pullup_required = True
                if any(c.type == "pullup_resistor" for c in instance.components):
                    group.pullup_covered = True
                address = _i2c_address(instance)
                if address:
                    if address in group.addresses.values():
                        conflict_owner = next(
                            mod for mod, addr in group.addresses.items()
                            if addr == address
                        )
                        message = (
                            f"I2C address conflict on {bus}: {instance.instance_id} "
                            f"and {conflict_owner} both use {address}"
                        )
                        group.conflicts.append(message)
                        result.errors.append(message)
                    group.addresses[instance.instance_id] = address

    graph.bus_groups = list(groups.values())


def _i2c_address(instance: ModuleInstance) -> str:
    for key in ("i2c_address", "address"):
        if key in instance.implementation_constraints:
            return str(instance.implementation_constraints[key])
    for component in instance.components:
        if component.role.startswith("i2c_address="):
            return component.role.split("=", 1)[1]
    return ""


def _build_power_domains(cfg: "ProjectConfig", graph: ModuleGraph) -> None:
    domains = {
        domain.name: PowerDomainUsage(
            domain_name=domain.name,
            max_current_ma=domain.max_current_ma,
        )
        for domain in cfg.hardware_platform.target_voltage_domains
        if domain.name
    }
    for instance in graph.instances:
        for domain_name in instance.voltage_domains + instance.rails:
            domain = domains.setdefault(
                domain_name,
                PowerDomainUsage(domain_name=domain_name),
            )
            domain.modules.append(instance.instance_id)
            domain.current_ma += _current_for_instance(instance)

    for domain in domains.values():
        if domain.max_current_ma and domain.current_ma > domain.max_current_ma:
            domain.warnings.append(
                f"estimated load {domain.current_ma:.1f}mA exceeds "
                f"budget {domain.max_current_ma:.1f}mA"
            )
    graph.power_domains = list(domains.values())


def _current_for_instance(instance: ModuleInstance) -> float:
    current = 0.0
    for component in instance.components:
        if component.role.startswith("current_ma="):
            try:
                current += float(component.role.split("=", 1)[1]) * component.count
            except ValueError:
                pass
    return current


def _slug(value: str) -> str:
    chars = []
    for ch in value:
        if ch.isalnum():
            chars.append(ch)
        else:
            chars.append("_")
    slug = "".join(chars).strip("_")
    return slug or "NET"
