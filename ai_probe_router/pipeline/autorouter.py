"""Autorouter pipeline stage and failure contract."""

from __future__ import annotations

from pathlib import Path

from ..config import ProjectConfig
from ..models.board import Board
from ..routing.freerouting_bridge import RoutingResult, route_board
from ..verification.report import CoverageReport


def run_autorouter(
    cfg: ProjectConfig,
    coverage: CoverageReport,
    board: Board | None,
    output_dir: Path,
    timeout_sec: float = 60.0,
) -> RoutingResult | None:
    """Export DSN, invoke FreeRouting, and record the signoff outcome."""
    if board is None:
        return None

    dsn_path = output_dir / "routing.dsn"
    result = route_board(board, dsn_path, output_dir, timeout_sec=timeout_sec)
    apply_autorouter_result(cfg, coverage, result)
    return result


def apply_autorouter_result(
    cfg: ProjectConfig,
    coverage: CoverageReport,
    result: RoutingResult,
) -> None:
    if result.ok:
        coverage.notes.append(f"Auto-routed in {result.duration_sec:.1f}s")
        return

    reason = result.error or "external autorouter did not complete"
    message = f"Auto-route failed: {reason}"
    coverage.notes.append(message)
    if cfg.process_controls.require_autorouter_feedback:
        raise RuntimeError(message)
