"""Tests for the autorouter pipeline stage contract."""

from __future__ import annotations

from pathlib import Path

from ai_probe_router.config import ProjectConfig
from ai_probe_router.models.board import Board
from ai_probe_router.pipeline import autorouter
from ai_probe_router.routing.freerouting_bridge import RoutingResult
from ai_probe_router.verification.report import CoverageReport


def test_autorouter_stage_records_success(tmp_path: Path, monkeypatch):
    board = Board()
    coverage = CoverageReport()
    calls = []

    def fake_route(board_arg, dsn_path, output_dir, **kwargs):
        calls.append((board_arg, dsn_path, output_dir, kwargs))
        return RoutingResult(ok=True, duration_sec=1.25)

    monkeypatch.setattr(autorouter, "route_board", fake_route)

    result = autorouter.run_autorouter(ProjectConfig(), coverage, board, tmp_path)

    assert result is not None
    assert result.ok
    assert coverage.notes == ["Auto-routed in 1.2s"]
    assert calls == [
        (
            board,
            tmp_path / "routing.dsn",
            tmp_path,
            {"timeout_sec": 60.0, "trace_width_um": 150, "clearance_um": 150},
        ),
    ]


def test_autorouter_stage_records_soft_failure(tmp_path: Path, monkeypatch):
    board = Board()
    coverage = CoverageReport()

    monkeypatch.setattr(
        autorouter,
        "route_board",
        lambda *args, **kwargs: RoutingResult(error="FreeRouting not found"),
    )

    result = autorouter.run_autorouter(ProjectConfig(), coverage, board, tmp_path)

    assert result is not None
    assert not result.ok
    assert coverage.notes == ["Auto-route failed: FreeRouting not found"]


def test_autorouter_stage_blocks_when_feedback_required(tmp_path: Path, monkeypatch):
    board = Board()
    coverage = CoverageReport()
    cfg = ProjectConfig()
    cfg.process_controls.require_autorouter_feedback = True

    monkeypatch.setattr(
        autorouter,
        "route_board",
        lambda *args, **kwargs: RoutingResult(error="FreeRouting failed"),
    )

    try:
        autorouter.run_autorouter(cfg, coverage, board, tmp_path)
    except RuntimeError as exc:
        assert "Auto-route failed: FreeRouting failed" in str(exc)
    else:
        raise AssertionError("required autorouter feedback should block failed routing")


def test_autorouter_stage_skips_without_board(tmp_path: Path, monkeypatch):
    calls = []

    monkeypatch.setattr(autorouter, "route_board", lambda *args, **kwargs: calls.append("route"))

    result = autorouter.run_autorouter(
        ProjectConfig(),
        CoverageReport(),
        None,
        tmp_path,
    )

    assert result is None
    assert calls == []


def test_autorouter_grid_backend_uses_grid_router(tmp_path: Path, monkeypatch):
    board = Board()
    coverage = CoverageReport()
    cfg = ProjectConfig()
    cfg.constraints.routing.backend = "grid"

    # Patch FreeRouting so we can prove it is NOT called
    freerouting_calls = []
    monkeypatch.setattr(
        autorouter,
        "route_board",
        lambda *a, **k: (freerouting_calls.append(1) or RoutingResult(ok=True)),
    )

    result = autorouter.run_autorouter(cfg, coverage, board, tmp_path)

    # Empty board = no nets to route = immediate success
    assert result is not None
    assert result.ok
    assert freerouting_calls == []


def test_autorouter_auto_fallback_to_grid(tmp_path: Path, monkeypatch):
    board = Board()
    coverage = CoverageReport()
    cfg = ProjectConfig()
    cfg.constraints.routing.backend = "auto"

    # FreeRouting fails
    monkeypatch.setattr(
        autorouter,
        "route_board",
        lambda *args, **kwargs: RoutingResult(error="FreeRouting not found"),
    )

    result = autorouter.run_autorouter(cfg, coverage, board, tmp_path)

    # Empty board means grid fallback succeeds immediately
    assert result is not None
    assert result.ok
    # A fallback note should be present
    assert any("FreeRouting failed" in n for n in coverage.notes)


def test_autorouter_invalid_backend_defaults_to_freerouting(tmp_path: Path, monkeypatch):
    board = Board()
    coverage = CoverageReport()
    cfg = ProjectConfig()
    cfg.constraints.routing.backend = "magic"

    calls = []
    monkeypatch.setattr(
        autorouter,
        "route_board",
        lambda *a, **k: (calls.append("freerouting") or RoutingResult(ok=True, duration_sec=1.0)),
    )

    result = autorouter.run_autorouter(cfg, coverage, board, tmp_path)

    assert result is not None
    assert result.ok
    assert "Unknown routing backend" in coverage.notes[0]
