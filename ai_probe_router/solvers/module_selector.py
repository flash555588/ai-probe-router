"""Rule-based functional-module selection.

This is the deterministic front door for schema v2. It keeps module selection
explainable while the CP-SAT resource allocator evolves behind the same model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..models.module import (
    FunctionalModule,
    ModuleDefinition,
    ModuleImplementation,
    SelectedModule,
    load_module_definition,
)


@dataclass
class ModuleSelectionResult:
    requested_count: int = 0
    selected: list[SelectedModule] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def select_modules(
    modules: list[FunctionalModule],
    library_dirs: list[str | Path] | None = None,
) -> ModuleSelectionResult:
    result = ModuleSelectionResult(requested_count=len(modules))
    library = load_module_library(library_dirs)

    for module in modules:
        definitions = [d for d in library if d.type == module.type]
        if not definitions:
            message = f"No module definition found for '{module.name}' (type={module.type})"
            if module.required:
                result.errors.append(message)
            else:
                result.warnings.append(message)
            continue

        viable: list[tuple[float, ModuleDefinition, ModuleImplementation, list[str]]] = []
        rejected: list[str] = []
        for definition in definitions:
            for implementation in definition.implementations:
                ok, reasons = _implementation_satisfies(module, implementation)
                if ok:
                    viable.append(
                        (
                            _score_implementation(implementation),
                            definition,
                            implementation,
                            reasons,
                        )
                    )
                else:
                    rejected.append(f"{definition.name}/{implementation.name}: {reasons[0]}")

        if not viable:
            message = f"No valid implementation found for '{module.name}' (type={module.type})"
            if module.required:
                result.errors.append(message)
            else:
                result.warnings.append(message)
            result.warnings.extend(rejected)
            continue

        _score, definition, implementation, reasons = min(viable, key=lambda item: item[0])
        result.selected.append(
            SelectedModule(
                module=module,
                definition=definition,
                implementation=implementation,
                reasons=reasons,
                rejected=rejected,
                review_required=bool(
                    implementation.constraints.get("human_review_required", False),
                ),
            )
        )

    return result


def load_module_library(
    library_dirs: list[str | Path] | None = None,
) -> list[ModuleDefinition]:
    if library_dirs is None:
        repo_root = Path(__file__).resolve().parents[2]
        library_dirs = [repo_root / "libraries" / "modules"]

    definitions: list[ModuleDefinition] = []
    for directory in library_dirs:
        root = Path(directory)
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.yaml")):
            definitions.append(load_module_definition(path))
    return definitions


def _implementation_satisfies(
    module: FunctionalModule,
    implementation: ModuleImplementation,
) -> tuple[bool, list[str]]:
    if (
        module.allowed_implementations
        and implementation.name not in module.allowed_implementations
    ):
        return False, [f"implementation not allowed by config: {implementation.name}"]

    if module.allowed_interfaces:
        if not implementation.interfaces:
            return False, ["implementation does not declare an interface"]
        if not set(module.allowed_interfaces) & set(implementation.interfaces):
            return False, [
                "interfaces do not match "
                f"requested={module.allowed_interfaces} available={implementation.interfaces}",
            ]

    if module.telemetry_bus:
        if module.telemetry_bus not in implementation.interfaces:
            return False, [f"telemetry bus '{module.telemetry_bus}' not supported"]

    if module.channels and implementation.channels:
        if implementation.channels < module.channels:
            return False, [
                f"only {implementation.channels} channels available; {module.channels} required",
            ]

    component_types = {component.type for component in implementation.components}
    features = {feature.upper() for feature in implementation.features}
    if module.require_level_shift and not (
        "level_shifter" in component_types or "LEVEL_SHIFT" in features
    ):
        return False, ["level shifting required but not provided"]
    if module.require_esd and not (
        "esd_array" in component_types or "ESD_PROTECTION" in features
    ):
        return False, ["ESD protection required but not provided"]
    if module.require_input_protection and not (
        component_types
        & {
            "esd_array",
            "rc_filter",
            "series_resistor",
            "resistor_array",
            "tvs_diode",
            "input_protection",
        }
    ):
        return False, ["input protection required but not provided"]
    if module.require_mux and "analog_mux" not in component_types:
        return False, ["mux required but not provided"]

    reasons = [f"selected implementation '{implementation.name}'"]
    if implementation.channels:
        reasons.append(f"supports {implementation.channels} channels")
    if implementation.interfaces:
        reasons.append(f"interfaces: {', '.join(implementation.interfaces)}")
    if implementation.constraints.get("human_review_required", False):
        reasons.append("human review required by implementation")
    return True, reasons


def _score_implementation(implementation: ModuleImplementation) -> float:
    component_count = sum(component.count for component in implementation.components)
    review_penalty = 1000.0 if implementation.constraints.get("human_review_required") else 0.0
    return (
        implementation.bom_cost * 100.0
        + implementation.area_mm2
        + component_count * 5.0
        + review_penalty
    )
