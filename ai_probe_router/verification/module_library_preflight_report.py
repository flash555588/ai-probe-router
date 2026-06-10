"""Preflight validation for schema-v2 module libraries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..models.module import FunctionalModule, load_module_definition
from ..models.module_library_preflight import (
    ModuleLibraryPreflightIssue,
    ModuleLibraryPreflightResult,
)

_KNOWN_TOP_LEVEL_KEYS = {
    "module",
    "provides",
    "requires",
    "implementations",
}

_KNOWN_COMPONENT_KEYS = {
    "type",
    "count",
    "role",
    "value",
    "value_options",
    "package_options",
    "chip",
    "version",
    "chip_version",
    "footprint_version",
    "alternate",
    "alternate_chips",
    "alternate_footprints",
}

_KNOWN_COMPONENT_TYPES = {
    "adc",
    "analog_mux",
    "audio_codec",
    "audio_dac",
    "bypass_capacitor",
    "cc_pull_down",
    "charge_pump_capacitor",
    "common_mode_choke",
    "connector",
    "crystal",
    "current_monitor",
    "current_sense_resistor",
    "decoupling_capacitor",
    "eeprom",
    "efuse",
    "esd_array",
    "esd_diode",
    "fuse",
    "gnss_receiver",
    "gpio_expander",
    "headphone_jack",
    "level_shifter",
    "lna",
    "lora_transceiver",
    "matching_network",
    "mcu_gpio",
    "motor_driver_ic",
    "output_coupling_capacitor",
    "pcb_antenna",
    "pd_controller",
    "pullup_resistor",
    "rc_filter",
    "resistor_array",
    "rs485_transceiver",
    "saw_filter",
    "sd_card_connector",
    "sense_resistor",
    "series_resistor",
    "testpad",
    "tvs_diode",
    "u_fl_connector",
    "usb_c_receptacle",
    "vbus_mosfet",
    "wifi_mcu",
}


def validate_module_library(
    requested_modules: list[FunctionalModule] | None = None,
    library_dirs: list[str | Path] | None = None,
) -> ModuleLibraryPreflightResult:
    result = ModuleLibraryPreflightResult()
    requested_modules = requested_modules or []
    library_roots = _library_dirs(library_dirs)
    result.library_dirs = [str(root) for root in library_roots]

    module_names: dict[str, str] = {}
    module_types: dict[str, list[str]] = {}
    loaded_types: set[str] = set()

    for root in library_roots:
        if not root.exists():
            _add(result, "warning", str(root), "module library directory is missing")
            continue
        for path in sorted(root.rglob("*.yaml")):
            raw = _read_yaml(path, result)
            if raw is None:
                continue
            identity = _validate_raw_module(path, raw, result)
            if identity is None:
                continue
            module_name, module_type = identity
            if module_name in module_names:
                _add(
                    result,
                    "error",
                    _rel(path),
                    f"duplicate module name '{module_name}' also in {module_names[module_name]}",
                )
            module_names[module_name] = _rel(path)
            module_types.setdefault(module_type, []).append(_rel(path))
            loaded_types.add(module_type)
            _count_loaded_definition(path, result)

    for module_type, paths in sorted(module_types.items()):
        if len(paths) > 1:
            _add(
                result,
                "warning",
                module_type,
                "multiple module definitions share this type: " + ", ".join(paths),
            )

    for module in requested_modules:
        if module.type in loaded_types:
            continue
        severity = "error" if module.required else "warning"
        _add(
            result,
            severity,
            module.name,
            f"requested module type '{module.type}' is not present in module library",
        )

    return result


def _library_dirs(library_dirs: list[str | Path] | None) -> list[Path]:
    if library_dirs is not None:
        return [Path(directory) for directory in library_dirs]
    package_root = Path(__file__).resolve().parents[1]
    return [package_root / "libraries" / "modules"]


def _read_yaml(
    path: Path,
    result: ModuleLibraryPreflightResult,
) -> dict[str, Any] | None:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - exact parser errors vary
        _add(result, "error", _rel(path), f"cannot read YAML: {exc}")
        return None
    if not isinstance(raw, dict):
        _add(result, "error", _rel(path), "module file must be a YAML mapping")
        return None
    return raw


def _validate_raw_module(
    path: Path,
    raw: dict[str, Any],
    result: ModuleLibraryPreflightResult,
) -> tuple[str, str] | None:
    unknown_top = sorted(set(raw) - _KNOWN_TOP_LEVEL_KEYS)
    for key in unknown_top:
        _add(result, "warning", _rel(path), f"unknown top-level key '{key}'")

    module = raw.get("module")
    if not isinstance(module, dict):
        _add(result, "error", _rel(path), "missing module mapping")
        return None
    module_name = str(module.get("name", "")).strip()
    module_type = str(module.get("type", "")).strip()
    if not module_name:
        _add(result, "error", _rel(path), "module.name is required")
    if not module_type:
        _add(result, "error", _rel(path), "module.type is required")
    if not module.get("version"):
        _add(result, "warning", _rel(path), "module.version is missing")

    implementations = raw.get("implementations")
    if not isinstance(implementations, list) or not implementations:
        _add(result, "error", _rel(path), "at least one implementation is required")
        return (module_name, module_type) if module_name and module_type else None

    seen_impls: set[str] = set()
    for index, impl in enumerate(implementations, start=1):
        _validate_implementation(path, index, impl, seen_impls, result)

    if module_name and module_type:
        return module_name, module_type
    return None


def _validate_implementation(
    path: Path,
    index: int,
    impl: Any,
    seen_impls: set[str],
    result: ModuleLibraryPreflightResult,
) -> None:
    label = f"{_rel(path)} implementation[{index}]"
    if not isinstance(impl, dict):
        _add(result, "error", label, "implementation must be a mapping")
        return
    name = str(impl.get("name", "")).strip()
    if not name:
        _add(result, "error", label, "implementation.name is required")
    elif name in seen_impls:
        _add(result, "error", label, f"duplicate implementation name '{name}'")
    seen_impls.add(name)

    if not impl.get("version"):
        _add(result, "warning", label, "implementation.version is missing")

    components = impl.get("components", [])
    if not isinstance(components, list):
        _add(result, "error", label, "components must be a list")
        return
    if not components:
        _add(result, "warning", label, "implementation has no components")
    for component_index, component in enumerate(components, start=1):
        _validate_component(path, name or str(index), component_index, component, result)


def _validate_component(
    path: Path,
    implementation_name: str,
    index: int,
    component: Any,
    result: ModuleLibraryPreflightResult,
) -> None:
    label = f"{_rel(path)} {implementation_name} component[{index}]"
    if not isinstance(component, dict):
        _add(result, "error", label, "component must be a mapping")
        return

    unknown_keys = sorted(set(component) - _KNOWN_COMPONENT_KEYS)
    for key in unknown_keys:
        _add(result, "warning", label, f"unknown component key '{key}'")

    component_type = str(component.get("type", "")).strip()
    if not component_type:
        _add(result, "error", label, "component.type is required")
    elif component_type not in _KNOWN_COMPONENT_TYPES:
        _add(result, "warning", label, f"unknown component type '{component_type}'")

    try:
        count = int(component.get("count", 1) or 1)
    except (TypeError, ValueError):
        _add(result, "error", label, "component.count must be an integer")
        return
    if count <= 0:
        _add(result, "error", label, "component.count must be greater than zero")

    if component.get("chip") and not component.get("chip_version"):
        _add(result, "warning", label, "chip_version is missing for chip component")
    package_options = component.get("package_options", [])
    if package_options and not component.get("footprint_version"):
        _add(result, "warning", label, "footprint_version is missing")


def _count_loaded_definition(
    path: Path,
    result: ModuleLibraryPreflightResult,
) -> None:
    try:
        definition = load_module_definition(path)
    except Exception as exc:
        _add(result, "error", _rel(path), f"loader failed: {exc}")
        return
    result.module_count += 1
    result.implementation_count += len(definition.implementations)
    result.component_count += sum(
        len(implementation.components)
        for implementation in definition.implementations
    )


def _add(
    result: ModuleLibraryPreflightResult,
    severity: str,
    path: str,
    message: str,
) -> None:
    result.issues.append(ModuleLibraryPreflightIssue(severity, path, message))


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


@dataclass
class ModuleLibraryPreflightReport:
    result: ModuleLibraryPreflightResult

    def summary_text(self) -> str:
        lines = [
            "=" * 96,
            "  AI Probe Router - Module Library Preflight Report",
            "=" * 96,
            "",
            f"  Library dirs:      {len(self.result.library_dirs)}",
            f"  Modules:           {self.result.module_count}",
            f"  Implementations:   {self.result.implementation_count}",
            f"  Components:        {self.result.component_count}",
            f"  Errors:            {len(self.result.errors)}",
            f"  Warnings:          {len(self.result.warnings)}",
            "",
        ]
        if self.result.library_dirs:
            lines.append("  Library Directories:")
            for directory in self.result.library_dirs:
                lines.append(f"    - {directory}")
            lines.append("")

        for title, issues in (
            ("Errors", self.result.errors),
            ("Warnings", self.result.warnings),
        ):
            if issues:
                lines.append(f"  {title}:")
                for issue in issues:
                    lines.append(f"    - {issue}")
                lines.append("")

        if not self.result.issues:
            lines.append("  No module library issues were reported.")
            lines.append("")

        lines.append("=" * 96)
        return "\n".join(lines)

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.summary_text(), encoding="utf-8")
