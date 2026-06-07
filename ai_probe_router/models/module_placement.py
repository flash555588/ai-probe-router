"""Hierarchical module placement plan models."""

from __future__ import annotations

from dataclasses import dataclass, field

from .board import BoundingBox


@dataclass
class ComponentPlacement:
    module_id: str
    refdes: str
    component_type: str
    role: str
    x: float
    y: float
    placement_class: str = "component"
    near_refdes: str = ""


@dataclass
class ModuleRegionPlan:
    module_id: str
    module_name: str
    module_type: str
    region: BoundingBox
    anchor: str = ""
    probe_zone: BoundingBox | None = None
    connector_zone: BoundingBox | None = None


@dataclass
class ModulePlacementPlan:
    regions: list[ModuleRegionPlan] = field(default_factory=list)
    components: list[ComponentPlacement] = field(default_factory=list)


@dataclass
class ModulePlacementResult:
    plan: ModulePlacementPlan = field(default_factory=ModulePlacementPlan)
    skipped: bool = False
    skip_reason: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.skipped and not self.errors

