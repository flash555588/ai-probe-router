from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RoutingRules:
    default_trace_width_mm: float = 0.15
    power_trace_width_mm: float = 0.5
    min_clearance_mm: float = 0.15
    max_vias_per_signal: int = 2
    avoid_under_components: bool = True


@dataclass
class PlacementRules:
    keep_probe_pads_on_grid: bool = True
    avoid_tall_components: bool = True
    min_distance_from_board_edge_mm: float = 2.0
    group_by_function: bool = True


@dataclass
class ManufacturingRules:
    min_trace_width_mm: float = 0.15
    min_clearance_mm: float = 0.15
    min_drill_mm: float = 0.3
    preferred_via_drill_mm: float = 0.3
    soldermask_expansion_mm: float = 0.05


@dataclass
class Constraints:
    routing: RoutingRules = None
    placement: PlacementRules = None
    manufacturing: ManufacturingRules = None

    def __post_init__(self):
        if self.routing is None:
            self.routing = RoutingRules()
        if self.placement is None:
            self.placement = PlacementRules()
        if self.manufacturing is None:
            self.manufacturing = ManufacturingRules()
