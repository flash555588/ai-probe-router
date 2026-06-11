"""Autorouter pipeline stage and failure contract."""

from __future__ import annotations

from pathlib import Path

from ..config import ProjectConfig
from ..models.board import Board
from ..routing.freerouting_bridge import RoutingResult, route_board
from ..solvers.grid_router import route_grid
from ..verification.report import CoverageReport

_VALID_BACKENDS = frozenset({"freerouting", "grid", "auto"})


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

    backend = cfg.constraints.routing.backend
    if backend not in _VALID_BACKENDS:
        coverage.notes.append(f"Unknown routing backend '{backend}'; defaulting to 'freerouting'")
        backend = "freerouting"

    if backend in ("freerouting", "auto"):
        result = _run_freerouting(cfg, board, output_dir, timeout_sec)
        if result.ok or backend == "freerouting":
            apply_autorouter_result(cfg, coverage, result)
            return result
        coverage.notes.append(
            f"FreeRouting failed ({result.error}); falling back to grid router"
        )

    if backend in ("grid", "auto"):
        result = _run_grid_fallback(cfg, coverage, board)
        apply_autorouter_result(cfg, coverage, result)
        return result

    return RoutingResult(ok=False, error=f"Unknown routing backend: {backend}")


def _run_freerouting(
    cfg: ProjectConfig,
    board: Board,
    output_dir: Path,
    timeout_sec: float,
) -> RoutingResult:
    """Run FreeRouting via DSN/SES round-trip."""
    trace_width_um = int(round(cfg.constraints.routing.default_trace_width_mm * 1000))
    clearance_um = int(round(cfg.constraints.routing.min_clearance_mm * 1000))

    dsn_path = output_dir / "routing.dsn"
    return route_board(
        board, dsn_path, output_dir, timeout_sec=timeout_sec,
        trace_width_um=trace_width_um, clearance_um=clearance_um,
    )


def _run_grid_fallback(
    cfg: ProjectConfig,
    coverage: CoverageReport,
    board: Board,
) -> RoutingResult:
    """Fallback single-net A* router when FreeRouting is unavailable.

    Iterates over nets that have testpoints but no recorded route length
    (Phase 1 failed or skipped) and attempts a simple pad-to-probe
    connection for each.
    """
    from ..eda_adapters.kicad.pcb_writer import add_track_segment
    routed = 0
    failed: list[str] = []

    for entry in coverage.entries:
        if not entry.has_testpoint or entry.trace_length_mm > 0:
            continue

        source_pads = board.find_pads_by_net(entry.net_name)
        probe_pads = [
            (fp.pads[0].x, fp.pads[0].y)
            for fp in board.footprints
            if fp.ref.startswith("TP") and fp.pads
            and fp.pads[0].net_name == entry.net_name
        ]

        if not source_pads or not probe_pads:
            failed.append(entry.net_name)
            continue

        sx, sy = source_pads[0][1].x, source_pads[0][1].y
        ex, ey = probe_pads[0]

        width = max(
            0.15, cfg.constraints.manufacturing.min_trace_width_mm,
            cfg.constraints.routing.default_trace_width_mm,
        )
        clearance = max(
            0.15, cfg.constraints.manufacturing.min_clearance_mm,
            cfg.constraints.routing.min_clearance_mm,
        )

        result = route_grid(
            board, entry.net_name, (sx, sy), (ex, ey),
            width=width, clearance=clearance, side=cfg.probe.side,
        )

        if result.ok:
            for a, b in zip(result.points, result.points[1:]):
                add_track_segment(
                    board, entry.net_name,
                    a[0], a[1], b[0], b[1],
                    width=width, side=cfg.probe.side,
                )
            routed += 1
        else:
            failed.append(entry.net_name)

    if failed:
        return RoutingResult(
            ok=False,
            error=f"Grid fallback: routed {routed} nets, failed {len(failed)}: {', '.join(failed)}",
        )

    return RoutingResult(
        ok=True,
        duration_sec=0.0,
        error=None,
    )


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
