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
    assert calls == [(board, tmp_path / "routing.dsn", tmp_path, {"timeout_sec": 60.0})]


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
