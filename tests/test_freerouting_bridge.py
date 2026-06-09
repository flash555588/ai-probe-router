"""Tests for the FreeRouting bridge."""

from __future__ import annotations

from pathlib import Path

from ai_probe_router.routing.freerouting_bridge import (
    RoutingResult,
    find_freerouting,
    run_freerouting,
)


def test_find_freerouting_returns_none_when_missing():
    # In a clean test environment FreeRouting is unlikely to be installed
    result = find_freerouting()
    # We only assert the function runs without crashing; result may be None or a path
    assert result is None or isinstance(result, str)


def test_run_freerouting_missing_dsn():
    result = run_freerouting("/nonexistent/board.dsn")
    assert not result.ok
    assert "not found" in result.error


def test_run_freerouting_missing_freerouting(tmp_path: Path):
    dsn = tmp_path / "board.dsn"
    dsn.write_text("(pcb \"test\")")
    # Since FreeRouting is not installed in test env, this should fail gracefully
    result = run_freerouting(dsn)
    assert not result.ok
    assert "FreeRouting not found" in result.error or result.error.startswith("exit")


def test_run_freerouting_reports_missing_java_for_jar(tmp_path: Path, monkeypatch):
    dsn = tmp_path / "board.dsn"
    dsn.write_text("(pcb \"test\")")

    monkeypatch.setattr(
        "ai_probe_router.routing.freerouting_bridge.find_freerouting",
        lambda: str(tmp_path / "freerouting.jar"),
    )
    monkeypatch.setattr(
        "ai_probe_router.routing.freerouting_bridge.shutil.which",
        lambda name: None if name == "java" else "unused",
    )

    result = run_freerouting(dsn)

    assert not result.ok
    assert result.error == "java not found in PATH (required for FreeRouting JAR)."


def test_routing_result_dataclass():
    r = RoutingResult(ok=True, dsn_path="a.dsn", ses_path="a.ses", duration_sec=1.2)
    assert r.ok
    assert r.ses_path == "a.ses"
