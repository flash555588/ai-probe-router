"""Tests for global placement and fixture design."""

from pathlib import Path

from ai_probe_router.models.board import Board, Footprint, Pad
from ai_probe_router.models.fixture_layout import DutPlacement, FixtureLayout
from ai_probe_router.models.probe import ProbeConfig, ProbeRequirement
from ai_probe_router.solvers.fixture_design import design_fixture
from ai_probe_router.solvers.global_placement import solve_global_placement


def test_global_placement_basic():
    from ai_probe_router.models.board import EdgeSegment
    board = Board(
        footprints=[
            Footprint(
                ref="U1",
                pads=[Pad(number="1", net_name="NET1", x=100.0, y=100.0, width=1.0, height=1.0)],
            )
        ],
        nets={"NET1": 1},
        edges=[
            EdgeSegment(80, 80, 120, 80),
            EdgeSegment(120, 80, 120, 120),
            EdgeSegment(120, 120, 80, 120),
            EdgeSegment(80, 120, 80, 80),
        ],
    )
    reqs = [ProbeRequirement(net_name="NET1", role="digital", required=True)]
    probe_cfg = ProbeConfig(min_spacing_mm=2.54)
    result = solve_global_placement(board, reqs, probe_cfg, grid_mm=5.0)
    assert result.solver_status != "ortools not installed"
    assert len(result.placements) == 1
    assert result.placements[0].net_name == "NET1"


def test_fixture_design_grid():
    board = Board(footprints=[], nets={})
    layout = FixtureLayout(
        dut_count=4,
        dut_spacing_x_mm=60.0,
        dut_spacing_y_mm=60.0,
        fixture_width_mm=200.0,
    )
    result = design_fixture(board, layout, Path("/tmp"))
    assert len(result.fixture_layout.dut_placements) == 4
    assert result.fixture_layout.dut_placements[0].x_mm == 30.0
    assert result.fixture_layout.dut_placements[0].y_mm == 30.0
    # 4 DUTs in 3-column grid: index 3 is col=0, row=1
    assert result.fixture_layout.dut_placements[3].x_mm == 30.0
    assert result.fixture_layout.dut_placements[3].y_mm == 90.0
    # index 2 is col=2, row=0
    assert result.fixture_layout.dut_placements[2].x_mm == 150.0
    assert result.fixture_layout.dut_placements[2].y_mm == 30.0
    assert result.fixture_layout.dut_placements[1].x_mm == 90.0
    assert result.fixture_layout.dut_placements[1].y_mm == 30.0



def test_fixture_layout_model():
    fp = FixtureLayout(
        dut_count=2,
        dut_spacing_x_mm=50.0,
        fixture_width_mm=150.0,
        fixture_height_mm=100.0,
    )
    assert fp.dut_count == 2
    assert fp.fixture_width_mm == 150.0


def test_dut_placement_model():
    dp = DutPlacement(index=0, x_mm=25.0, y_mm=30.0, rotation_deg=90.0)
    assert dp.index == 0
    assert dp.rotation_deg == 90.0
