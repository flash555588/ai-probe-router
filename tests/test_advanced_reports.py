from ai_probe_router.config import ProjectConfig
from ai_probe_router.models.board import Board, EdgeSegment
from ai_probe_router.models.design_graph import RoutingStrategy
from ai_probe_router.models.module import FunctionalModule
from ai_probe_router.routing.module_corridor import analyze_routing_feasibility
from ai_probe_router.solvers.module_graph import build_module_graph
from ai_probe_router.solvers.module_selector import select_modules
from ai_probe_router.verification.bom_report import BomReport
from ai_probe_router.verification.bus_report import BusReport
from ai_probe_router.verification.module_graph_report import ModuleGraphReport
from ai_probe_router.verification.power_report import PowerReport
from ai_probe_router.verification.routing_feasibility_report import RoutingFeasibilityReport


def test_advanced_reports_include_module_data(tmp_path):
    modules = [
        FunctionalModule(name="analog", type="analog_measurement", telemetry_bus="i2c"),
    ]
    cfg = ProjectConfig(schema_version=2, functional_modules=modules)
    graph_result = build_module_graph(cfg, select_modules(modules))

    graph_text = ModuleGraphReport(graph_result).summary_text()
    bus_text = BusReport(graph_result).summary_text()
    power_text = PowerReport(graph_result).summary_text()

    assert "MOD1 analog" in graph_text
    assert "I2C" in bus_text
    assert "Power Domain Report" in power_text

    bom_path = tmp_path / "bom_report.csv"
    BomReport(graph_result).write(bom_path)
    bom_text = bom_path.read_text(encoding="utf-8")
    assert "module_id,module_name" in bom_text
    assert "MOD1,analog" in bom_text


def test_routing_feasibility_report_text():
    board = Board(
        edges=[
            EdgeSegment(0, 0, 40, 0),
            EdgeSegment(40, 0, 40, 40),
            EdgeSegment(40, 40, 0, 40),
            EdgeSegment(0, 40, 0, 0),
        ],
        raw=["kicad_pcb"],
    )
    modules = [
        FunctionalModule(name="debug", type="debug_swd"),
        FunctionalModule(name="fixture", type="protected_probe_fixture", depends_on=["debug"]),
    ]
    cfg = ProjectConfig(schema_version=2, functional_modules=modules)
    graph_result = build_module_graph(cfg, select_modules(modules), board)
    routing = analyze_routing_feasibility(board, graph_result.graph, RoutingStrategy())

    text = RoutingFeasibilityReport(routing).summary_text()

    assert "Routing Feasibility Report" in text
    assert "Corridors:" in text
    assert "MOD" in text

