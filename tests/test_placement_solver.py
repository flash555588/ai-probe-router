"""Tests for placement solver."""

from ai_probe_router.models.board import Board, EdgeSegment, Footprint, Pad
from ai_probe_router.models.constraints import Constraints
from ai_probe_router.models.probe import ProbeConfig, ProbeRequirement
from ai_probe_router.solvers.constraint_checker import check_placement
from ai_probe_router.solvers.placement_solver import find_placement, place_pogo_array


def _make_board() -> Board:
    fp = Footprint(
        ref="U1", value="STM32", x=100, y=100,
        pads=[
            Pad(number="1", x=95, y=96.5, net_name="SWDIO", net_id=3),
            Pad(number="24", x=100, y=95, net_name="GND", net_id=1),
        ],
    )
    return Board(
        footprints=[fp],
        nets={"": 0, "GND": 1, "3V3": 2, "SWDIO": 3},
        edges=[
            EdgeSegment(80, 80, 120, 80),
            EdgeSegment(120, 80, 120, 120),
            EdgeSegment(120, 120, 80, 120),
            EdgeSegment(80, 120, 80, 80),
        ],
    )


def test_placement_inside_board():
    board = _make_board()
    req = ProbeRequirement(net_name="SWDIO", role="debug")
    probe = ProbeConfig(preferred_grid_mm=2.54)
    x, y = find_placement(board, req, probe, Constraints(), [])
    bounds = board.board_bounds()
    assert bounds.contains(x, y)


def test_placement_away_from_component():
    board = _make_board()
    req = ProbeRequirement(net_name="SWDIO", role="debug")
    probe = ProbeConfig(preferred_grid_mm=2.54, pad_diameter_mm=1.5)
    x, y = find_placement(board, req, probe, Constraints(), [])
    assert check_placement(x, y, board, Constraints(), probe).ok


def test_placement_respects_spacing():
    board = _make_board()
    probe = ProbeConfig(preferred_grid_mm=2.54, min_spacing_mm=2.54)
    req1 = ProbeRequirement(net_name="SWDIO", role="debug")
    x1, y1 = find_placement(board, req1, probe, Constraints(), [])

    req2 = ProbeRequirement(net_name="GND", role="ground")
    x2, y2 = find_placement(board, req2, probe, Constraints(), [(x1, y1)])

    import math
    dist = math.hypot(x2 - x1, y2 - y1)
    assert dist >= probe.min_spacing_mm or dist == 0


def test_placement_snaps_to_grid():
    board = _make_board()
    req = ProbeRequirement(net_name="SWDIO", role="debug")
    probe = ProbeConfig(preferred_grid_mm=2.54)
    x, y = find_placement(board, req, probe, Constraints(), [])
    assert abs(x - round(x / 2.54) * 2.54) < 0.01
    assert abs(y - round(y / 2.54) * 2.54) < 0.01


def test_placement_with_no_pads():
    board = Board(
        footprints=[],
        nets={"MYSTERY": 1},
        edges=[
            EdgeSegment(0, 0, 40, 0),
            EdgeSegment(40, 0, 40, 40),
            EdgeSegment(40, 40, 0, 40),
            EdgeSegment(0, 40, 0, 0),
        ],
    )
    req = ProbeRequirement(net_name="MYSTERY", role="digital")
    assert find_placement(board, req, ProbeConfig(), Constraints(), []) is None


def test_multiple_placements_spread():
    board = _make_board()
    probe = ProbeConfig(preferred_grid_mm=2.54, min_spacing_mm=2.54)
    placed = []
    for i in range(4):
        req = ProbeRequirement(net_name="GND", role="ground")
        x, y = find_placement(board, req, probe, Constraints(), placed, index=i)
        placed.append((x, y))
    assert len(placed) == 4
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            assert placed[i] != placed[j]


def test_pogo_array_positions():
    board = _make_board()
    reqs = [
        ProbeRequirement(net_name="A", role="debug"),
        ProbeRequirement(net_name="B", role="debug"),
        ProbeRequirement(net_name="C", role="debug"),
    ]
    probe = ProbeConfig(
        style=ProbeConfig().style, preferred_grid_mm=2.54,
    )
    positions = place_pogo_array(board, reqs, probe, Constraints())
    assert len(positions) == 3
    # Should be aligned to grid
    for x, y in positions:
        assert abs(x - round(x / 2.54) * 2.54) < 0.01
        assert abs(y - round(y / 2.54) * 2.54) < 0.01


def test_pogo_array_inside_board():
    board = _make_board()
    reqs = [ProbeRequirement(net_name="A", role="debug") for _ in range(4)]
    positions = place_pogo_array(board, reqs, ProbeConfig(), Constraints())
    bounds = board.board_bounds()
    for x, y in positions:
        assert bounds.contains(x, y)


def test_pogo_array_no_board_fallback():
    board = Board(footprints=[], nets={}, edges=[])
    reqs = [ProbeRequirement(net_name="A", role="debug") for _ in range(2)]
    positions = place_pogo_array(board, reqs, ProbeConfig(), Constraints())
    assert len(positions) == 2
    assert positions[0] != positions[1]
