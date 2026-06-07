from ai_probe_router.config import ProjectConfig
from ai_probe_router.models.board import Board, EdgeSegment
from ai_probe_router.models.module import FunctionalModule
from ai_probe_router.solvers.module_graph import build_module_graph
from ai_probe_router.solvers.module_placement import plan_module_placement
from ai_probe_router.solvers.module_selector import select_modules
from ai_probe_router.verification.module_placement_report import ModulePlacementReport


def _board() -> Board:
    return Board(
        edges=[
            EdgeSegment(0, 0, 80, 0),
            EdgeSegment(80, 0, 80, 50),
            EdgeSegment(80, 50, 0, 50),
            EdgeSegment(0, 50, 0, 0),
        ],
        raw=["kicad_pcb"],
    )


def _graph(modules):
    cfg = ProjectConfig(schema_version=2, functional_modules=modules)
    return build_module_graph(cfg, select_modules(modules), _board()).graph


def test_module_placement_assigns_regions_and_components():
    graph = _graph([
        FunctionalModule(name="debug", type="debug_swd", preferred_region="probe_edge"),
        FunctionalModule(name="analog", type="analog_measurement", preferred_region="top"),
    ])

    result = plan_module_placement(graph, _board())

    assert result.ok
    assert len(result.plan.regions) == 2
    assert len(result.plan.components) > 0
    assert all(instance.region is not None for instance in graph.instances)
    assert any(comp.refdes.startswith("U") for comp in result.plan.components)


def test_module_placement_skips_without_board_outline():
    graph = _graph([FunctionalModule(name="debug", type="debug_swd")])

    result = plan_module_placement(graph, Board(raw=["kicad_pcb"]))

    assert result.skipped
    assert result.skip_reason == "no_board_outline"


def test_module_placement_report_text():
    graph = _graph([FunctionalModule(name="analog", type="analog_measurement")])
    result = plan_module_placement(graph, _board())

    text = ModulePlacementReport(result).summary_text()

    assert "Module Placement Report" in text
    assert "MOD1" in text
    assert "Component Placements" in text

