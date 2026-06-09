"""Schema-v2 module planning pipeline stage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import ProjectConfig
from ..models.board import Board
from ..routing.module_corridor import analyze_routing_feasibility
from ..solvers.module_graph import build_module_graph
from ..solvers.module_placement import plan_module_placement
from ..solvers.module_selector import select_modules
from ..verification.bom_report import BomReport
from ..verification.bus_report import BusReport
from ..verification.module_compatibility_report import (
    ModuleCompatibilityReport,
    analyze_module_compatibility,
)
from ..verification.module_graph_report import ModuleGraphReport
from ..verification.module_instantiation_report import ModuleInstantiationReport
from ..verification.module_library_preflight_report import (
    ModuleLibraryPreflightReport,
    validate_module_library,
)
from ..verification.module_placement_report import ModulePlacementReport
from ..verification.module_report import ModuleReport
from ..verification.power_report import PowerReport
from ..verification.routing_feasibility_report import RoutingFeasibilityReport


@dataclass
class ModulePlanningResult:
    module_library_preflight_result: object | None = None
    module_selection: object | None = None
    module_graph_result: object | None = None
    module_placement_result: object | None = None
    module_instantiation_result: object | None = None
    module_compatibility_result: object | None = None
    routing_feasibility: object | None = None
    resource_allocation_result: object | None = None
    footprint_preview_result: object | None = None

    @property
    def blocked(self) -> bool:
        return module_plan_blocked(
            self.module_library_preflight_result,
            self.module_selection,
            self.module_graph_result,
            self.module_compatibility_result,
            self.resource_allocation_result,
            self.footprint_preview_result,
        )


def run_module_planning(
    cfg: ProjectConfig,
    board: Board | None,
) -> ModulePlanningResult:
    result = ModulePlanningResult()
    if not cfg.functional_modules:
        return result

    result.module_library_preflight_result = validate_module_library(cfg.functional_modules)
    if module_plan_blocked(
        result.module_library_preflight_result,
        result.module_selection,
        result.module_graph_result,
        result.module_compatibility_result,
        result.resource_allocation_result,
    ):
        return result

    result.module_selection = select_modules(cfg.functional_modules)
    if cfg.resource_allocator.enable and result.module_selection is not None:
        from ..solvers.resource_allocator import allocate_resources

        result.resource_allocation_result = allocate_resources(
            result.module_selection.selected,
            cfg,
        )
    result.module_graph_result = build_module_graph(cfg, result.module_selection, board)
    result.module_compatibility_result = analyze_module_compatibility(
        result.module_graph_result,
    )
    if module_plan_blocked(
        result.module_library_preflight_result,
        result.module_selection,
        result.module_graph_result,
        result.module_compatibility_result,
        result.resource_allocation_result,
    ):
        return result

    result.module_placement_result = plan_module_placement(
        result.module_graph_result.graph,
        board,
    )
    if cfg.module_footprint_preview.enable and result.module_selection is not None:
        from ..solvers.module_footprint_planner import plan_module_footprints

        result.footprint_preview_result = plan_module_footprints(
            result.module_selection.selected,
            board,
            cfg.module_footprint_preview,
        )
    result.routing_feasibility = analyze_routing_feasibility(
        board,
        result.module_graph_result.graph,
        cfg.routing_strategy,
    )
    return result


def module_plan_blocked(
    module_library_preflight_result,
    module_selection,
    module_graph_result,
    module_compatibility_result,
    resource_allocation_result=None,
    footprint_preview_result=None,
) -> bool:
    return any(
        result is not None and not result.ok
        for result in (
            module_library_preflight_result,
            module_selection,
            module_graph_result,
            module_compatibility_result,
            resource_allocation_result,
            footprint_preview_result,
        )
    )


def write_module_planning_reports(
    out_dir: Path,
    run_id: str,
    result: ModulePlanningResult,
) -> None:
    if result.module_library_preflight_result is not None:
        ModuleLibraryPreflightReport(result.module_library_preflight_result).write(
            out_dir / "module_library_preflight_report.txt",
        )
    if result.module_selection is not None:
        ModuleReport(result.module_selection).write(out_dir / "module_report.txt")
    if result.module_graph_result is not None:
        ModuleGraphReport(result.module_graph_result).write(out_dir / "module_graph_report.txt")
        BusReport(result.module_graph_result).write(out_dir / "bus_report.txt")
        PowerReport(result.module_graph_result).write(out_dir / "power_report.txt")
        BomReport(result.module_graph_result, run_id=run_id).write(out_dir / "bom_report.csv")
    if result.module_compatibility_result is not None:
        ModuleCompatibilityReport(result.module_compatibility_result).write(
            out_dir / "module_compatibility_report.txt",
        )
    if result.module_placement_result is not None:
        ModulePlacementReport(result.module_placement_result).write(
            out_dir / "module_placement_report.txt",
        )
    if result.module_instantiation_result is not None:
        ModuleInstantiationReport(result.module_instantiation_result).write(
            out_dir / "module_instantiation_report.txt",
        )
    if result.routing_feasibility is not None:
        RoutingFeasibilityReport(result.routing_feasibility).write(
            out_dir / "routing_feasibility_report.txt",
        )
    if result.resource_allocation_result is not None:
        from ..solvers.resource_allocator_report import write_resource_allocation_report

        write_resource_allocation_report(result.resource_allocation_result, out_dir)
    if result.footprint_preview_result is not None:
        from ..verification.footprint_preview_report import write_footprint_preview_report

        write_footprint_preview_report(result.footprint_preview_result, out_dir)
