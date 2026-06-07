"""Tests for constraint checker."""


from ai_probe_router.eda_adapters.kicad.pcb_writer import add_track_segment
from ai_probe_router.models.board import Board, EdgeSegment, Footprint, Pad
from ai_probe_router.models.constraints import Constraints, PlacementRules
from ai_probe_router.models.probe import ProbeConfig
from ai_probe_router.solvers.constraint_checker import (
    check_placement,
    placement_clearance_margin,
    validate_all_probes,
)


def _make_board(edges=True) -> Board:
    fp = Footprint(
        ref="U1", value="STM32", x=100, y=100,
        pads=[
            Pad(number="1", x=95, y=96.5, net_name="SWDIO", net_id=3),
            Pad(number="24", x=100, y=95, net_name="GND", net_id=1),
        ],
    )
    edge_list = []
    if edges:
        edge_list = [
            EdgeSegment(80, 80, 120, 80),
            EdgeSegment(120, 80, 120, 120),
            EdgeSegment(120, 120, 80, 120),
            EdgeSegment(80, 120, 80, 80),
        ]
    return Board(
        footprints=[fp],
        nets={"": 0, "GND": 1, "3V3": 2, "SWDIO": 3},
        edges=edge_list,
    )


def test_valid_placement():
    board = _make_board()
    result = check_placement(110, 110, board, Constraints(), ProbeConfig())
    assert result.ok


def test_outside_board():
    board = _make_board()
    result = check_placement(130, 100, board, Constraints(), ProbeConfig())
    assert not result.ok
    assert any(v.rule == "outside_board" for v in result.violations)


def test_board_edge_clearance():
    board = _make_board()
    constraints = Constraints()
    constraints.placement = PlacementRules(min_distance_from_board_edge_mm=3.0)
    result = check_placement(81, 100, board, constraints, ProbeConfig())
    assert not result.ok
    assert any(v.rule == "board_edge_clearance" for v in result.violations)


def test_component_collision():
    board = _make_board()
    # (95, 96.5) is directly on pad 1 of U1
    result = check_placement(95, 96.5, board, Constraints(), ProbeConfig())
    assert not result.ok
    assert any(v.rule == "component_collision" for v in result.violations)


def test_probe_spacing():
    board = _make_board()
    existing = [(110, 110)]
    probe = ProbeConfig(min_spacing_mm=2.54)
    result = check_placement(111, 110, board, Constraints(), probe, existing)
    assert not result.ok
    assert any(v.rule == "probe_spacing" for v in result.violations)


def test_probe_spacing_ok():
    board = _make_board()
    existing = [(110, 110)]
    probe = ProbeConfig(min_spacing_mm=2.54)
    result = check_placement(115, 110, board, Constraints(), probe, existing)
    assert result.ok


def test_no_board_outline_warning():
    board = _make_board(edges=False)
    result = check_placement(100, 100, board, Constraints(), ProbeConfig())
    assert result.ok
    assert any(v.rule == "board_outline" and v.severity == "warning" for v in result.violations)


def test_validate_all_probes():
    board = _make_board()
    probes = [
        (110, 110, "SWDIO"),
        (115, 110, "GND"),
    ]
    result = validate_all_probes(probes, board, Constraints(), ProbeConfig(min_spacing_mm=2.54))
    assert result.ok


def test_validate_all_probes_spacing_fail():
    board = _make_board()
    probes = [
        (110, 110, "SWDIO"),
        (111, 110, "GND"),
    ]
    result = validate_all_probes(probes, board, Constraints(), ProbeConfig(min_spacing_mm=2.54))
    assert not result.ok


def test_testpoint_not_checked_for_collision():
    fp = Footprint(ref="TP1", value="TestPoint", x=110, y=110, pads=[
        Pad(number="1", x=110, y=110, net_name="SWDIO"),
    ])
    board = Board(
        footprints=[fp],
        nets={"SWDIO": 1},
        edges=[
            EdgeSegment(80, 80, 120, 80),
            EdgeSegment(120, 80, 120, 120),
            EdgeSegment(120, 120, 80, 120),
            EdgeSegment(80, 120, 80, 80),
        ],
    )
    result = check_placement(110, 110, board, Constraints(), ProbeConfig())
    assert result.ok


def test_probe_placement_respects_different_net_track_clearance():
    board = _make_board()
    add_track_segment(board, "UART_RX", 100, 102, 100, 108, width=0.2)

    result = check_placement(
        100, 104, board, Constraints(), ProbeConfig(), net_name="3V3",
    )
    assert not result.ok
    assert any(v.rule == "track_clearance" for v in result.violations)

    same_net = check_placement(
        100, 104, board, Constraints(), ProbeConfig(), net_name="UART_RX",
    )
    assert same_net.ok


def test_rotated_pad_collision_detected():
    # A 10x1 mm pad rotated 45 degrees at (100, 100)
    # Pad local corners at (-5, -0.5) and (5, 0.5); rotated and translated
    # Pad center is at (100, 100)
    fp = Footprint(
        ref="U2", value="Rotated", x=100, y=100, rotation=45,
        pads=[
            Pad(
                number="1",
                x=100,
                y=100,
                width=10.0,
                height=1.0,
                rotation=45,
                net_name="NET",
            ),
        ],
    )
    board = Board(
        footprints=[fp],
        nets={"NET": 1},
        edges=[
            EdgeSegment(50, 50, 150, 50),
            EdgeSegment(150, 50, 150, 150),
            EdgeSegment(150, 150, 50, 150),
            EdgeSegment(50, 150, 50, 50),
        ],
    )
    # KiCad board rotations are clockwise because the board Y axis points downward.
    result = check_placement(103, 97, board, Constraints(), ProbeConfig(pad_diameter_mm=1.0))
    assert not result.ok
    assert any(v.rule == "component_collision" for v in result.violations)


def test_unrotated_rect_pad_corner_does_not_false_collide():
    fp = Footprint(
        ref="U2", value="Rect", x=100, y=100,
        pads=[
            Pad(number="1", x=100, y=100, width=10.0, height=1.0, net_name="NET"),
        ],
    )
    board = Board(
        footprints=[fp],
        nets={"NET": 1},
        edges=[
            EdgeSegment(50, 50, 150, 50),
            EdgeSegment(150, 50, 150, 150),
            EdgeSegment(150, 150, 50, 150),
            EdgeSegment(50, 150, 50, 50),
        ],
    )
    result = check_placement(103, 103, board, Constraints(), ProbeConfig(pad_diameter_mm=1.0))
    assert result.ok


def test_placement_clearance_margin_scores_extra_room():
    board = Board(
        footprints=[
            Footprint(
                ref="U3",
                pads=[
                    Pad(number=str(i), x=10 + i * 0.5, y=10, width=0.28, height=1.2)
                    for i in range(16)
                ],
            ),
        ],
        edges=[
            EdgeSegment(0, 0, 40, 0),
            EdgeSegment(40, 0, 40, 30),
            EdgeSegment(40, 30, 0, 30),
            EdgeSegment(0, 30, 0, 0),
        ],
    )
    constraints = Constraints()
    probe = ProbeConfig(pad_diameter_mm=1.0)
    near = placement_clearance_margin(14.0, 11.8, board, constraints, probe)
    far = placement_clearance_margin(30.0, 20.0, board, constraints, probe)
    assert far > near
