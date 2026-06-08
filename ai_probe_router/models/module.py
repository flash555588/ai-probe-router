"""Functional hardware module models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AiHint:
    hint_type: str
    target: str = ""
    value: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    ignored_reason: str = ""

    @property
    def supported(self) -> bool:
        return not self.ignored_reason


@dataclass
class FunctionalModule:
    name: str
    type: str
    required: bool = True
    priority: int = 0
    target_nets: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    channels: int = 0
    voltage_domains: list[str] = field(default_factory=list)
    allowed_implementations: list[str] = field(default_factory=list)
    allowed_interfaces: list[str] = field(default_factory=list)
    rails: list[str] = field(default_factory=list)
    telemetry_bus: str = ""
    resolution_bits_min: int = 0
    budget_area_mm2: float = 0.0
    preferred_region: str = ""
    version: str = ""
    ai_hints: list[AiHint] = field(default_factory=list)
    require_level_shift: bool = False
    require_esd: bool = False
    require_input_protection: bool = False
    require_mux: bool = False
    params: dict[str, Any] = field(default_factory=dict)

@dataclass
class ComponentSpec:
    type: str
    count: int = 1
    role: str = ""
    value_options: list[str] = field(default_factory=list)
    package_options: list[str] = field(default_factory=list)
    chip: str = ""
    version: str = ""
    chip_version: str = ""
    footprint_version: str = ""
    alternate_chips: list[str] = field(default_factory=list)
    alternate_footprints: list[str] = field(default_factory=list)


@dataclass
class ModuleImplementation:
    name: str
    version: str = ""
    components: list[ComponentSpec] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    interfaces: list[str] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    channels: int = 0
    area_mm2: float = 0.0
    bom_cost: float = 0.0


@dataclass
class ModuleDefinition:
    name: str
    type: str
    version: str = ""
    provides: list[str] = field(default_factory=list)
    target_nets: list[str] = field(default_factory=list)
    implementations: list[ModuleImplementation] = field(default_factory=list)


@dataclass
class SelectedModule:
    module: FunctionalModule
    definition: ModuleDefinition
    implementation: ModuleImplementation
    reasons: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    review_required: bool = False


def parse_functional_module(raw: dict[str, Any]) -> FunctionalModule:
    known_keys = {
        "name",
        "type",
        "required",
        "priority",
        "target_nets",
        "depends_on",
        "channels",
        "voltage_domains",
        "allowed_implementations",
        "allowed_interfaces",
        "rails",
        "telemetry_bus",
        "resolution_bits_min",
        "budget_area_mm2",
        "preferred_region",
        "version",
        "ai_hints",
        "require_level_shift",
        "require_esd",
        "require_input_protection",
        "require_mux",
    }
    return FunctionalModule(
        name=str(raw.get("name", "")),
        type=str(raw.get("type", "")),
        required=bool(raw.get("required", True)),
        priority=int(raw.get("priority", 0) or 0),
        target_nets=[str(n) for n in raw.get("target_nets", [])],
        depends_on=[str(n) for n in raw.get("depends_on", [])],
        channels=int(raw.get("channels", 0) or 0),
        voltage_domains=[str(d) for d in raw.get("voltage_domains", [])],
        allowed_implementations=[str(i) for i in raw.get("allowed_implementations", [])],
        allowed_interfaces=[str(i) for i in raw.get("allowed_interfaces", [])],
        rails=[str(r) for r in raw.get("rails", [])],
        telemetry_bus=str(raw.get("telemetry_bus", "")),
        resolution_bits_min=int(raw.get("resolution_bits_min", 0) or 0),
        budget_area_mm2=float(raw.get("budget_area_mm2", 0.0) or 0.0),
        preferred_region=str(raw.get("preferred_region", "")),
        version=str(raw.get("version", "")),
        ai_hints=[
            parse_ai_hint(hint)
            for hint in raw.get("ai_hints", [])
        ],
        require_level_shift=bool(raw.get("require_level_shift", False)),
        require_esd=bool(raw.get("require_esd", False)),
        require_input_protection=bool(raw.get("require_input_protection", False)),
        require_mux=bool(raw.get("require_mux", False)),
        params={k: v for k, v in raw.items() if k not in known_keys},
    )


_SUPPORTED_AI_HINTS = {
    "prefer_region",
    "avoid_region",
    "keep_near",
    "keep_away_from",
    "sensitive_route",
}


def parse_ai_hint(raw: Any) -> AiHint:
    if isinstance(raw, str):
        hint = AiHint(hint_type=raw)
    elif isinstance(raw, dict):
        known = {"type", "target", "value"}
        hint = AiHint(
            hint_type=str(raw.get("type", "")),
            target=str(raw.get("target", "")),
            value=str(raw.get("value", "")),
            params={k: v for k, v in raw.items() if k not in known},
        )
    else:
        return AiHint(hint_type="", ignored_reason="AI hint must be a string or mapping")

    if hint.hint_type not in _SUPPORTED_AI_HINTS:
        hint.ignored_reason = f"unsupported AI hint type: {hint.hint_type}"
    return hint


def load_module_definition(path: str | Path) -> ModuleDefinition:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Module definition must be a YAML mapping: {path}")

    module = raw.get("module", {})
    if not isinstance(module, dict):
        raise ValueError(f"Module definition missing 'module' mapping: {path}")

    implementations = []
    for impl in raw.get("implementations", []):
        if not isinstance(impl, dict):
            continue
        components = [
            ComponentSpec(
                type=str(comp.get("type", "")),
                count=int(comp.get("count", 1) or 1),
                role=str(comp.get("role", "")),
                value_options=[str(v) for v in comp.get("value_options", [])],
                package_options=[str(v) for v in comp.get("package_options", [])],
                chip=str(comp.get("chip", "")),
                version=str(comp.get("version", "")),
                chip_version=str(comp.get("chip_version", "")),
                footprint_version=str(comp.get("footprint_version", "")),
                alternate_chips=[
                    str(v) for v in comp.get("alternate_chips", [])
                ],
                alternate_footprints=[
                    str(v) for v in comp.get("alternate_footprints", [])
                ],
            )
            for comp in impl.get("components", [])
            if isinstance(comp, dict)
        ]
        implementations.append(
            ModuleImplementation(
                name=str(impl.get("name", "")),
                version=str(impl.get("version", "")),
                components=components,
                constraints=dict(impl.get("constraints", {})),
                interfaces=[str(v) for v in impl.get("interfaces", [])],
                features=[str(v) for v in impl.get("features", [])],
                channels=int(impl.get("channels", 0) or 0),
                area_mm2=float(impl.get("area_mm2", 0.0) or 0.0),
                bom_cost=float(impl.get("bom_cost", 0.0) or 0.0),
            )
        )

    return ModuleDefinition(
        name=str(module.get("name", "")),
        type=str(module.get("type", "")),
        version=str(module.get("version", "")),
        provides=[str(v) for v in raw.get("provides", [])],
        target_nets=[str(v) for v in raw.get("requires", {}).get("target_nets", [])],
        implementations=implementations,
    )
