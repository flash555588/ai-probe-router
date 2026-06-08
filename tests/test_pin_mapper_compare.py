"""Tests for pin mapper compare mode."""

from __future__ import annotations

from ai_probe_router.config import ProjectConfig
from ai_probe_router.engine import _run_phase2
from ai_probe_router.models.dev_board import DevBoardPin, DevelopmentBoard
from ai_probe_router.models.probe import ProbeRequirement
from ai_probe_router.solvers.pin_mapper_compare import compare_pin_mappers


def test_compare_mode_keeps_greedy_output_by_default(tmp_path):
    cfg = ProjectConfig()
    cfg.pin_mapper.mode = "compare"
    cfg.pin_mapper.selected_output = "greedy"
    cfg.nets_to_expose = [ProbeRequirement(net_name="SIG", role="digital", required=True)]
    board = _difference_board()

    report = _run_phase2(cfg, None, None, board, tmp_path)

    assert report.result.assignments[0].pin_name == "P1_SIMPLE"
    assert (tmp_path / "pin_mapper_compare_report.txt").exists()
    assert (tmp_path / "pin_mapper_compare_report.json").exists()


def test_compare_mode_reports_assignment_differences():
    result = compare_pin_mappers(
        [ProbeRequirement(net_name="SIG", role="digital", required=True)],
        _difference_board(),
    )

    assert result.differences
    assert result.differences[0].net_name == "SIG"
    assert "PIN_MAPPER_COMPARE_DIFFERENCE" in result.warnings


def _difference_board() -> DevelopmentBoard:
    return DevelopmentBoard(
        name="dev",
        connector_type="header",
        rows=1,
        pins_per_row=2,
        pins=[
            DevBoardPin(name="P0_MULTI", capabilities=["GPIO", "ADC1"]),
            DevBoardPin(name="P1_SIMPLE", capabilities=["GPIO"]),
        ],
    )
