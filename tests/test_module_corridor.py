from ai_probe_router.config import ProjectConfig
from ai_probe_router.models.board import Board, BoundingBox, EdgeSegment, Footprint, Pad
from ai_probe_router.models.design_graph import RoutingStrategy
from ai_probe_router.models.module import FunctionalModule, parse_ai_hint
from ai_probe_router.routing.module_corridor import analyze_routing_feasibility
from ai_probe_router.solvers.module_graph import build_module_graph
from ai_probe_router.solvers.module_selector import select_modules
from ai_probe_router.verification.routing_feasibility_report import RoutingFeasibilityReport


def _board() -> Board:
    return Board(
        edges=[
            EdgeSegment(0, 0, 60, 0),
            EdgeSegment(60, 0, 60, 40),
            EdgeSegment(60, 40, 0, 40),
            EdgeSegment(0, 40, 0, 0),
        ],
        raw=["kicad_pcb"],
    )


def _graph(modules):
    cfg = ProjectConfig(schema_version=2, functional_modules=modules)
    return build_module_graph(cfg, select_modules(modules), _board()).graph


def test_corridor_planner_finds_path_on_simple_board():
    graph = _graph([
        FunctionalModule(name="debug", type="debug_swd"),
        FunctionalModule(name="fixture", type="protected_probe_fixture", depends_on=["debug"]),
    ])

    result = analyze_routing_feasibility(_board(), graph, RoutingStrategy(coarse_grid_mm=5))

    assert not result.skipped
    assert result.corridors
    assert all(corridor.ok for corridor in result.corridors)
    assert result.corridors[0].length_mm > 0


def test_congestion_score_increases_when_corridors_overlap():
    graph = _graph([
        FunctionalModule(name="debug", type="debug_swd", preferred_region="right"),
        FunctionalModule(
            name="fixture_a",
            type="protected_probe_fixture",
            preferred_region="left",
            depends_on=["debug"],
        ),
        FunctionalModule(
            name="fixture_b",
            type="protected_probe_fixture",
            preferred_region="left",
            depends_on=["debug"],
        ),
    ])

    result = analyze_routing_feasibility(_board(), graph, RoutingStrategy(coarse_grid_mm=5))

    assert any(corridor.congestion_score > 0 for corridor in result.corridors)
    assert result.congestion_hotspots


def test_capacity_penalty_increases_when_corridors_exceed_layers():
    graph = _graph([
        FunctionalModule(name="debug", type="debug_swd", preferred_region="right"),
        FunctionalModule(
            name="fixture_a",
            type="protected_probe_fixture",
            preferred_region="left",
            depends_on=["debug"],
        ),
        FunctionalModule(
            name="fixture_b",
            type="protected_probe_fixture",
            preferred_region="left",
            depends_on=["debug"],
        ),
    ])

    result = analyze_routing_feasibility(
        _board(),
        graph,
        RoutingStrategy(coarse_grid_mm=5, max_corridor_layers=1),
    )

    assert any(corridor.capacity_penalty > 0 for corridor in result.corridors)
    assert any("exceed layer capacity" in warning for warning in result.warnings)


def test_corridor_planner_routes_around_footprint_obstacle():
    board = _board()
    board.footprints.append(
        Footprint(
            ref="U1",
            x=30,
            y=20,
            pads=[
                Pad(
                    number="1",
                    x=30,
                    y=20,
                    width=12,
                    height=12,
                    shape="rect",
                ),
            ],
        )
    )
    graph = _graph([
        FunctionalModule(name="debug", type="debug_swd"),
        FunctionalModule(name="fixture", type="protected_probe_fixture", depends_on=["debug"]),
    ])
    graph.instances[0].region = BoundingBox(8, 18, 12, 22)
    graph.instances[1].region = BoundingBox(48, 18, 52, 22)

    result = analyze_routing_feasibility(
        board,
        graph,
        RoutingStrategy(coarse_grid_mm=2),
    )
    corridor = result.corridors[0]
    obstacle = BoundingBox(23.5, 13.5, 36.5, 26.5)

    assert corridor.ok
    assert result.hard_obstacle_count > 0
    assert corridor.obstacle_penalty > 0
    assert not any(obstacle.contains(*point) for point in corridor.points[1:-1])


def test_sensitive_route_penalty_near_noisy_module():
    graph = _graph([
        FunctionalModule(
            name="analog",
            type="analog_measurement",
            preferred_region="left",
            depends_on=["debug"],
            ai_hints=[parse_ai_hint({"type": "sensitive_route"})],
        ),
        FunctionalModule(name="debug", type="debug_swd", preferred_region="right"),
        FunctionalModule(name="gpio", type="gpio_expansion", preferred_region="center"),
    ])

    result = analyze_routing_feasibility(
        _board(),
        graph,
        RoutingStrategy(coarse_grid_mm=5, sensitive_net_spacing_mm=100),
    )

    assert any(corridor.sensitive_penalty > 0 for corridor in result.corridors)


def test_no_board_outline_skips_routing_feasibility():
    graph = _graph([
        FunctionalModule(name="debug", type="debug_swd"),
    ])

    result = analyze_routing_feasibility(Board(raw=["kicad_pcb"]), graph, RoutingStrategy())

    assert result.skipped
    assert result.skip_reason == "no_board_outline"


def test_routing_feasibility_report_includes_capacity_and_obstacles():
    graph = _graph([
        FunctionalModule(name="debug", type="debug_swd"),
        FunctionalModule(name="fixture", type="protected_probe_fixture", depends_on=["debug"]),
    ])

    result = analyze_routing_feasibility(
        _board(),
        graph,
        RoutingStrategy(coarse_grid_mm=5, max_corridor_layers=1),
    )

    text = RoutingFeasibilityReport(result).summary_text()

    assert "Hard obstacles:" in text
    assert "Grid capacity:" in text
    assert "cap=" in text
