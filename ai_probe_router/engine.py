"""Core engine: orchestrates Phase 1 (testpoints) and Phase 2 (pin mapping)."""

from __future__ import annotations

from pathlib import Path

from .ai.net_classifier import classify_net
from .config import ProjectConfig
from .eda_adapters.kicad.cli_runner import run_drc, run_erc
from .eda_adapters.kicad.pcb_parser import parse_pcb
from .eda_adapters.kicad.pcb_writer import (
    add_connector_footprint,
    add_testpoint_footprint,
    write_pcb,
)
from .eda_adapters.kicad.sch_parser import parse_schematic
from .eda_adapters.kicad.sch_writer import (
    add_connector_symbol,
    add_testpoint_symbol,
    write_schematic,
)
from .models.board import Board, Schematic
from .models.dev_board import DevelopmentBoard
from .models.probe import ProbeRequirement
from .solvers.constraint_checker import validate_all_probes
from .solvers.pin_mapper import solve_mapping
from .solvers.placement_solver import find_placement
from .verification.pin_report import PinMapReport
from .verification.report import CoverageReport, NetCoverage


def run(cfg: ProjectConfig, project_dir: str | Path) -> tuple[CoverageReport, PinMapReport | None]:
    base = Path(project_dir)
    sch_path = base / cfg.schematic_file
    pcb_path = base / cfg.board_file

    board: Board | None = None
    sch: Schematic | None = None

    if pcb_path.exists():
        board = parse_pcb(pcb_path)
    if sch_path.exists():
        sch = parse_schematic(sch_path)

    pin_report: PinMapReport | None = None
    if cfg.development_board is not None and cfg.nets_to_expose:
        pin_report = _run_phase2(cfg, board, sch, cfg.development_board)

    coverage = _run_phase1(cfg, board, sch)

    out_dir = base / "output"
    out_dir.mkdir(exist_ok=True)

    if board is not None:
        # Run constraint validation on placed probes
        probe_data = [
            (e.probe_x, e.probe_y, e.net_name)
            for e in coverage.entries if e.has_testpoint
        ]
        if probe_data:
            validation = validate_all_probes(
                probe_data, board, cfg.constraints, cfg.probe,
            )
            coverage.constraint_violations = len(validation.violations)
            coverage.constraint_ok = validation.ok
            coverage.constraint_messages = [v.message for v in validation.violations]

        out_pcb = out_dir / pcb_path.name
        write_pcb(board, out_pcb)

    if sch is not None:
        out_sch = out_dir / sch_path.name
        write_schematic(sch, out_sch)

    if board is not None and (out_dir / pcb_path.name).exists():
        drc = run_drc(out_dir / pcb_path.name, out_dir)
        coverage.drc_ok = drc.ok
        coverage.drc_violations = len(drc.violations)

    if sch is not None and (out_dir / sch_path.name).exists():
        erc = run_erc(out_dir / sch_path.name, out_dir)
        coverage.erc_ok = erc.ok
        coverage.erc_violations = len(erc.violations)

    report_path = out_dir / "testpoint_report.txt"
    coverage.write(report_path)
    if pin_report is not None:
        pin_report.write(out_dir / "pin_mapping_report.txt")

    return coverage, pin_report


def _run_phase1(
    cfg: ProjectConfig,
    board: Board | None,
    sch: Schematic | None,
) -> CoverageReport:
    report = CoverageReport(total_nets_requested=len(cfg.nets_to_expose))
    tp_counter = _next_tp_ref(board)
    placed_probes: list[tuple[float, float]] = []

    for req in cfg.nets_to_expose:
        role = classify_net(req.net_name)
        count = max(req.duplicate_probe_count, 1)
        placed = False
        px, py = 0.0, 0.0

        for i in range(count):
            ref = f"TP{tp_counter}"
            tp_counter += 1

            if board is not None:
                x, y = find_placement(
                    board, req, cfg.probe, cfg.constraints,
                    placed_probes, index=i,
                )
                px, py = x, y
                add_testpoint_footprint(
                    board, req.net_name, x, y,
                    ref=ref, pad_diameter=cfg.probe.pad_diameter_mm,
                    side=cfg.probe.side,
                )
                placed_probes.append((x, y))
                placed = True

            if sch is not None and i == 0:
                sx, sy = _find_sch_placement(sch, req, cfg)
                add_testpoint_symbol(sch, req.net_name, sx, sy, ref=ref)

        report.entries.append(NetCoverage(
            net_name=req.net_name, role=role, required=req.required,
            has_testpoint=placed, probe_x=px, probe_y=py, side=cfg.probe.side,
        ))
        if placed:
            report.covered += 1
        else:
            report.missing += 1

    return report


def _run_phase2(
    cfg: ProjectConfig,
    board: Board | None,
    sch: Schematic | None,
    dev_board: DevelopmentBoard,
) -> PinMapReport:
    result = solve_mapping(cfg.nets_to_expose, dev_board)
    pin_report = PinMapReport(
        board_name=dev_board.name,
        result=result,
    )

    if result.assignments:
        if sch is not None:
            add_connector_symbol(
                sch, result.assignments,
                ref="J1",
                x=80.0, y=50.0,
                rows=2,
                pins_per_row=20,
            )
        if board is not None:
            add_connector_footprint(
                board, result.assignments,
                ref="J1",
                x=150.0, y=100.0,
                rows=2,
                pins_per_row=20,
                pitch=dev_board.pitch_mm,
                side=cfg.probe.side,
            )

    return pin_report


def _next_tp_ref(board: Board | None) -> int:
    if board is None:
        return 1
    max_n = 0
    for fp in board.footprints:
        if fp.ref.startswith("TP") and fp.ref[2:].isdigit():
            max_n = max(max_n, int(fp.ref[2:]))
    return max_n + 1


def _find_sch_placement(
    sch: Schematic, req: ProbeRequirement, cfg: ProjectConfig,
) -> tuple[float, float]:
    for lb in sch.labels:
        if lb["name"] == req.net_name:
            return lb["x"] + 5.08, lb["y"]
    y_base = 20.0 + len(sch.components) * 5.08
    return 40.0, y_base
