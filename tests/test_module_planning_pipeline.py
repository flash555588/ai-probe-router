"""Tests for the schema-v2 module planning pipeline stage."""

from __future__ import annotations

from pathlib import Path

from ai_probe_router.config import ProjectConfig
from ai_probe_router.models.board import Board, EdgeSegment
from ai_probe_router.models.module import FunctionalModule
from ai_probe_router.pipeline.module_planning import (
    module_plan_blocked,
    run_module_planning,
    write_module_planning_reports,
)


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


def test_module_planning_skips_when_no_modules():
    result = run_module_planning(ProjectConfig(), _board())

    assert not result.blocked
    assert result.module_selection is None
    assert result.module_graph_result is None


def test_module_planning_runs_selection_graph_placement_and_reports(tmp_path: Path):
    cfg = ProjectConfig(
        schema_version=2,
        functional_modules=[
            FunctionalModule(name="debug_access", type="debug_swd"),
            FunctionalModule(
                name="power_observation",
                type="current_voltage_monitor",
                rails=["VDD_3V3"],
            ),
        ],
    )

    result = run_module_planning(cfg, _board())
    write_module_planning_reports(tmp_path, "APR-MODULE", result)

    assert not result.blocked
    assert result.module_library_preflight_result is not None
    assert result.module_selection is not None
    assert result.module_graph_result is not None
    assert result.module_compatibility_result is not None
    assert result.module_placement_result is not None
    assert result.routing_feasibility is not None
    assert (tmp_path / "module_report.txt").is_file()
    assert (tmp_path / "module_graph_report.txt").is_file()
    assert (tmp_path / "module_placement_report.txt").is_file()
    assert (tmp_path / "routing_feasibility_report.txt").is_file()
    assert (tmp_path / "bom_report.csv").is_file()


def test_module_planning_blocks_on_invalid_required_module(tmp_path: Path):
    cfg = ProjectConfig(
        schema_version=2,
        functional_modules=[
            FunctionalModule(name="missing", type="not_in_library", required=True),
        ],
    )

    result = run_module_planning(cfg, _board())
    write_module_planning_reports(tmp_path, "APR-MODULE", result)

    assert result.blocked
    assert module_plan_blocked(
        result.module_library_preflight_result,
        result.module_selection,
        result.module_graph_result,
        result.module_compatibility_result,
    )
    assert result.module_selection is None
    assert (tmp_path / "module_library_preflight_report.txt").is_file()
