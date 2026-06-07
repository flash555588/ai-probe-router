"""Schema-v2 design intent models."""

from __future__ import annotations

from dataclasses import dataclass, field

from .module import FunctionalModule
from .power_domain import PowerDomain


@dataclass
class DesignGoals:
    optimize_for: list[str] = field(default_factory=list)
    max_added_area_mm2: float = 0.0
    preferred_side: str = ""
    human_review_required_for: list[str] = field(default_factory=list)


@dataclass
class HardwarePlatform:
    target_voltage_domains: list[PowerDomain] = field(default_factory=list)


@dataclass
class ModulePlacementRules:
    group_by_module: bool = True
    keep_power_modules_near_input: bool = True
    keep_analog_modules_away_from_switching_power: bool = True
    keep_debug_near_board_edge: bool = True
    max_module_to_probe_distance_mm: float = 0.0


@dataclass
class RoutingStrategy:
    coarse_grid_mm: float = 5.0
    max_corridor_layers: int = 2
    congestion_weight: float = 10.0
    via_weight: float = 8.0
    length_weight: float = 1.0
    sensitive_net_spacing_mm: float = 5.0


@dataclass
class DesignGraph:
    modules: list[FunctionalModule] = field(default_factory=list)
    hardware_platform: HardwarePlatform = field(default_factory=HardwarePlatform)
    design_goals: DesignGoals = field(default_factory=DesignGoals)
    routing_strategy: RoutingStrategy = field(default_factory=RoutingStrategy)
