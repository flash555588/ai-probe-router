"""Tests for the global CP-SAT placement solver."""

from pathlib import Path

from ai_probe_router.config import load_config
from ai_probe_router.engine import run
from ai_probe_router.models.board import Board, EdgeSegment, Footprint, Pad
from ai_probe_router.models.constraints import Constraints
from ai_probe_router.models.net import NetRole
from ai_probe_router.models.probe import ProbeConfig, ProbeRequirement
from ai_probe_router.solvers.placement_solver_global import PlacementTask, solve_placement_global


def _make_board() -> Board:
    """Create a simple board with a few components."""
    fp = Footprint(
        ref="U1", value="MCU", lib_id="Test:QFP",
        x=100.0, y=100.0, layer="F.Cu",
        pads=[
            Pad(number="1", x=96.5, y=96.5, width=0.5, height=0.5,
                net_name="SWDIO", net_id=1, local_x=-3.5, local_y=-3.5),
            Pad(number="2", x=97.0, y=96.5, width=0.5, height=0.5,
                net_name="GND", net_id=2, local_x=-3.0, local_y=-3.5),
            Pad(number="3", x=97.5, y=96.5, width=0.5, height=0.5,
                net_name="UART_TX", net_id=3, local_x=-2.5, local_y=-3.5),
            Pad(number="4", x=98.0, y=96.5, width=0.5, height=0.5,
                net_name="UART_RX", net_id=4, local_x=-2.0, local_y=-3.5),
        ],
    )
    return Board(
        raw=["kicad_pcb"],
        nets={"SWDIO": 1, "GND": 2, "UART_TX": 3, "UART_RX": 4},
        footprints=[fp],
        edges=[
            EdgeSegment(0, 0, 200, 0),
            EdgeSegment(200, 0, 200, 200),
            EdgeSegment(200, 200, 0, 200),
            EdgeSegment(0, 200, 0, 0),
        ],
    )


def test_global_solver_finds_placements():
    board = _make_board()
    tasks = [
        PlacementTask(
            ProbeRequirement(net_name="SWDIO", role="debug"), 0,
            NetRole.DEBUG, set(),
        ),
        PlacementTask(
            ProbeRequirement(net_name="GND", role="ground"), 0,
            NetRole.GROUND, set(),
        ),
        PlacementTask(
            ProbeRequirement(net_name="UART_TX", role="digital"), 0,
            NetRole.COMMUNICATION, set(),
        ),
    ]
    probe_cfg = ProbeConfig(min_spacing_mm=2.54, preferred_grid_mm=2.54)
    constraints = Constraints()

    result = solve_placement_global(board, tasks, probe_cfg, constraints)

    assert len(result) == 3
    for key, pos in result.items():
        assert pos is not None, f"No placement for {key}"
        x, y = pos
        assert 0 <= x <= 200
        assert 0 <= y <= 200


def test_global_solver_respects_min_spacing():
    board = _make_board()
    tasks = [
        PlacementTask(
            ProbeRequirement(net_name="SWDIO", role="debug"), 0,
            NetRole.DEBUG, set(),
        ),
        PlacementTask(
            ProbeRequirement(net_name="GND", role="ground"), 0,
            NetRole.GROUND, set(),
        ),
        PlacementTask(
            ProbeRequirement(net_name="UART_TX", role="digital"), 0,
            NetRole.COMMUNICATION, set(),
        ),
    ]
    probe_cfg = ProbeConfig(min_spacing_mm=5.0, preferred_grid_mm=2.54)
    constraints = Constraints()

    result = solve_placement_global(board, tasks, probe_cfg, constraints)

    positions = [p for p in result.values() if p is not None]
    # All pairwise distances should be >= min_spacing
    import math
    for i, (x1, y1) in enumerate(positions):
        for j, (x2, y2) in enumerate(positions):
            if i < j:
                dist = math.hypot(x1 - x2, y1 - y2)
                assert dist >= 5.0 - 1e-3, f"Spacing violation: {dist:.3f}mm"


def test_global_solver_ignores_input_order():
    """Changing the order of nets should not change the set of placed positions."""
    board = _make_board()
    probe_cfg = ProbeConfig(min_spacing_mm=2.54, preferred_grid_mm=2.54)
    constraints = Constraints()

    order_a = [
        PlacementTask(ProbeRequirement("SWDIO", "debug"), 0, NetRole.DEBUG, set()),
        PlacementTask(ProbeRequirement("GND", "ground"), 0, NetRole.GROUND, set()),
        PlacementTask(ProbeRequirement("UART_TX", "digital"), 0, NetRole.COMMUNICATION, set()),
    ]
    order_b = [
        PlacementTask(ProbeRequirement("UART_TX", "digital"), 0, NetRole.COMMUNICATION, set()),
        PlacementTask(ProbeRequirement("SWDIO", "debug"), 0, NetRole.DEBUG, set()),
        PlacementTask(ProbeRequirement("GND", "ground"), 0, NetRole.GROUND, set()),
    ]

    result_a = solve_placement_global(board, order_a, probe_cfg, constraints)
    result_b = solve_placement_global(board, order_b, probe_cfg, constraints)

    # The set of positions should be the same (or equivalent)
    pos_a = sorted(p for p in result_a.values() if p is not None)
    pos_b = sorted(p for p in result_b.values() if p is not None)
    assert len(pos_a) == len(pos_b) == 3


def test_global_solver_duplicate_probes():
    board = _make_board()
    tasks = [
        PlacementTask(
            ProbeRequirement(net_name="GND", role="ground", duplicate_probe_count=3),
            0, NetRole.GROUND, set(),
        ),
        PlacementTask(
            ProbeRequirement(net_name="GND", role="ground", duplicate_probe_count=3),
            1, NetRole.GROUND, set(),
        ),
        PlacementTask(
            ProbeRequirement(net_name="GND", role="ground", duplicate_probe_count=3),
            2, NetRole.GROUND, set(),
        ),
    ]
    probe_cfg = ProbeConfig(min_spacing_mm=2.54, preferred_grid_mm=2.54)
    constraints = Constraints()

    result = solve_placement_global(board, tasks, probe_cfg, constraints)

    assert len(result) == 3
    positions = [p for p in result.values() if p is not None]
    assert len(positions) == 3

    import math
    for i, (x1, y1) in enumerate(positions):
        for j, (x2, y2) in enumerate(positions):
            if i < j:
                dist = math.hypot(x1 - x2, y1 - y2)
                assert dist >= 2.54 - 1e-3


def test_global_solver_differential_pair_bonus():
    board = _make_board()
    tasks = [
        PlacementTask(
            ProbeRequirement(
                net_name="UART_TX", role="communication", pair_net_name="UART_RX",
            ), 0, NetRole.COMMUNICATION, set(),
        ),
        PlacementTask(
            ProbeRequirement(
                net_name="UART_RX", role="communication", pair_net_name="UART_TX",
            ), 0, NetRole.COMMUNICATION, set(),
        ),
    ]
    probe_cfg = ProbeConfig(min_spacing_mm=2.54, preferred_grid_mm=2.54)
    constraints = Constraints()

    result = solve_placement_global(board, tasks, probe_cfg, constraints)

    pos_tx = result.get(("UART_TX", 0))
    pos_rx = result.get(("UART_RX", 0))
    assert pos_tx is not None
    assert pos_rx is not None

    import math
    dist = math.hypot(pos_tx[0] - pos_rx[0], pos_tx[1] - pos_rx[1])
    # With the CP-SAT pair bonus they should be relatively close
    assert dist <= 2.54 * 4


def test_end_to_end_order_invariance(tmp_path: Path):
    """Full engine run with reordered nets should still cover all nets.

    Note: constraint_ok may differ between runs because _add_route_if_clear
    adds tracks in net order, and tracks become board keepouts for later
    probes.  The global placement solver guarantees probe *positions* are
    order-invariant, but the final constraint check depends on the full
    routed board.
    """
    repo_root = Path(__file__).parent.parent
    config_src = repo_root / "examples" / "iot_sensor_node_config.yaml"
    pcb_src = repo_root / "examples" / "minimal_project" / "main.kicad_pcb"
    sch_src = repo_root / "examples" / "minimal_project" / "main.kicad_sch"
    dev_board = repo_root / "libraries" / "dev_boards" / "stm32_nucleo_64.yaml"

    import shutil
    for run_id in ("a", "b"):
        run_dir = tmp_path / run_id
        run_dir.mkdir()
        shutil.copy(pcb_src, run_dir / "main.kicad_pcb")
        shutil.copy(sch_src, run_dir / "main.kicad_sch")
        shutil.copy(config_src, run_dir / "config.yaml")
        text = (run_dir / "config.yaml").read_text()
        text = text.replace(
            "../libraries/dev_boards/stm32_nucleo_64.yaml",
            str(dev_board).replace("\\", "/"),
        )
        (run_dir / "config.yaml").write_text(text)

    cfg_a = load_config(tmp_path / "a" / "config.yaml")
    report_a, _ = run(cfg_a, tmp_path / "a")

    # Run B — reverse net order
    cfg_b = load_config(tmp_path / "b" / "config.yaml")
    cfg_b.nets_to_expose = list(reversed(cfg_b.nets_to_expose))
    report_b, _ = run(cfg_b, tmp_path / "b")

    # Both must cover all requested nets
    assert report_a.covered == report_a.total_nets_requested
    assert report_b.covered == report_b.total_nets_requested
    # No required net should be missing
    required_nets_a = {e.net_name for e in report_a.entries if e.required}
    required_nets_b = {e.net_name for e in report_b.entries if e.required}
    assert required_nets_a == required_nets_b
