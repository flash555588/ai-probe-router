"""Core engine: orchestrates Phase 1 (testpoints) and Phase 2 (pin mapping)."""

from __future__ import annotations

from pathlib import Path

from .ai.net_classifier import classify_net
from .config import ProjectConfig
from .eda_adapters.kicad.cli_runner import run_drc, run_erc
from .eda_adapters.kicad.pcb_parser import parse_pcb
from .eda_adapters.kicad.pcb_writer import (
    add_connector_footprint,
    add_fiducial_footprint,
    add_keepout_zone,
    add_protection_footprint,
    add_testpoint_footprint,
    add_tooling_hole_footprint,
    write_pcb,
)
from .eda_adapters.kicad.sch_parser import parse_schematic
from .eda_adapters.kicad.sch_writer import (
    add_connector_symbol,
    add_protected_testpoint_symbol,
    add_testpoint_symbol,
    write_schematic,
)
from .models.board import Board, Schematic
from .models.dev_board import DevelopmentBoard
from .models.net import NetRole
from .models.probe import ProbeRequirement, ProbeStyle
from .routing.dsn_export import export_dsn
from .solvers.constraint_checker import validate_all_probes
from .solvers.pin_mapper import solve_mapping
from .solvers.placement_solver import find_placement, place_pogo_array
from .verification.manufacturing_report import generate_manufacturing_report
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

    mfg_report = generate_manufacturing_report(board, coverage)
    mfg_report.write(out_dir / "manufacturing_report.txt")

    if board is not None:
        export_dsn(board, out_dir / "routing.dsn")

    return coverage, pin_report


def _run_phase1(
    cfg: ProjectConfig,
    board: Board | None,
    sch: Schematic | None,
) -> CoverageReport:
    report = CoverageReport(total_nets_requested=len(cfg.nets_to_expose))
    tp_counter = _next_tp_ref(board)
    prot_counter = _next_prot_ref(board)
    placed_probes: list[tuple[float, float]] = []

    is_pogo = cfg.probe.style == ProbeStyle.POGO_PAD
    pogo_positions: list[tuple[float, float]] = []
    if is_pogo and board is not None:
        expanded_reqs = _expand_reqs(cfg.nets_to_expose)
        pogo_positions = place_pogo_array(
            board, expanded_reqs, cfg.probe, cfg.constraints,
        )

    pos_index = 0
    for req in cfg.nets_to_expose:
        role = classify_net(req.net_name)
        count = max(req.duplicate_probe_count, 1)
        placed = False
        px, py = 0.0, 0.0
        protection = cfg.protection.get_protection(req.role)

        for i in range(count):
            tp_ref = f"TP{tp_counter}"
            tp_counter += 1

            if board is not None:
                if is_pogo and pos_index < len(pogo_positions):
                    x, y = pogo_positions[pos_index]
                else:
                    x, y = find_placement(
                        board, req, cfg.probe, cfg.constraints,
                        placed_probes, index=i,
                    )
                pos_index += 1
                px, py = x, y

                if protection is not None:
                    probe_net = f"PROBE_{req.net_name}"
                    prot_ref = f"{protection.ref_prefix}{prot_counter}"
                    prot_counter += 1
                    add_protection_footprint(
                        board, req.net_name, probe_net,
                        x - 2.0, y,
                        protection,
                        ref=prot_ref, side=cfg.probe.side,
                    )
                    add_testpoint_footprint(
                        board, probe_net, x, y,
                        ref=tp_ref, pad_diameter=cfg.probe.pad_diameter_mm,
                        side=cfg.probe.side,
                    )
                else:
                    add_testpoint_footprint(
                        board, req.net_name, x, y,
                        ref=tp_ref, pad_diameter=cfg.probe.pad_diameter_mm,
                        side=cfg.probe.side,
                    )

                placed_probes.append((x, y))
                placed = True

                # Add keepout zone around probe pad
                keepout_margin = 1.0
                keepout_size = cfg.probe.pad_diameter_mm + keepout_margin * 2
                add_keepout_zone(
                    board, x, y, keepout_size, keepout_size,
                )

            if sch is not None and i == 0:
                sx, sy = _find_sch_placement(sch, req, cfg)
                if protection is not None:
                    prot_sch_ref = f"{protection.ref_prefix}{prot_counter - 1}"
                    add_protected_testpoint_symbol(
                        sch, req.net_name, sx, sy,
                        protection,
                        tp_ref=tp_ref, prot_ref=prot_sch_ref,
                    )
                else:
                    add_testpoint_symbol(sch, req.net_name, sx, sy, ref=tp_ref)

        review_needed = role in {
            NetRole.HIGH_SPEED, NetRole.CLOCK, NetRole.ANALOG,
        } or req.current_ma > 500

        trace_w, clearance = _net_class_for_role(role, req.current_ma)

        report.entries.append(NetCoverage(
            net_name=req.net_name, role=role, required=req.required,
            has_testpoint=placed, probe_x=px, probe_y=py, side=cfg.probe.side,
            review_required=review_needed,
            trace_width_mm=trace_w,
            clearance_mm=clearance,
        ))
        if placed:
            report.covered += 1
        else:
            report.missing += 1

    if board is not None:
        _place_fiducials_and_tooling(board, cfg)

    return report


def _place_fiducials_and_tooling(board: Board, cfg: ProjectConfig) -> None:
    bounds = board.board_bounds()
    if bounds is None:
        return

    edge = cfg.constraints.placement.min_distance_from_board_edge_mm
    fid_offset = max(edge, 3.0)

    if cfg.probe.require_fiducials:
        # Three fiducials: bottom-left, bottom-right, top-left
        fid_positions = [
            (bounds.min_x + fid_offset, bounds.min_y + fid_offset),
            (bounds.max_x - fid_offset, bounds.min_y + fid_offset),
            (bounds.min_x + fid_offset, bounds.max_y - fid_offset),
        ]
        for i, (fx, fy) in enumerate(fid_positions, start=1):
            add_fiducial_footprint(board, fx, fy, ref=f"FID{i}")

    if cfg.probe.require_tooling_holes:
        # Two tooling holes along bottom edge, spaced from corners
        th_offset = max(edge, 5.0)
        th_positions = [
            (bounds.min_x + th_offset, bounds.min_y + th_offset),
            (bounds.max_x - th_offset, bounds.min_y + th_offset),
        ]
        for i, (tx, ty) in enumerate(th_positions, start=1):
            add_tooling_hole_footprint(board, tx, ty, ref=f"TH{i}")


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
            # Keepout around connector
            conn_w = 20 * dev_board.pitch_mm
            conn_h = 2 * dev_board.pitch_mm
            add_keepout_zone(
                board, 150.0 + conn_w / 2, 100.0 + conn_h / 2,
                conn_w + 2.0, conn_h + 2.0,
            )

    return pin_report


def _net_class_for_role(role: NetRole, current_ma: float) -> tuple[float, float]:
    if role == NetRole.POWER:
        if current_ma > 500:
            return 0.5, 0.2
        return 0.3, 0.15
    if role == NetRole.GROUND:
        return 0.3, 0.15
    if role == NetRole.HIGH_SPEED:
        return 0.15, 0.2
    if role == NetRole.ANALOG:
        return 0.2, 0.25
    if role == NetRole.CLOCK:
        return 0.15, 0.2
    return 0.15, 0.15


def _expand_reqs(reqs: list[ProbeRequirement]) -> list[ProbeRequirement]:
    result: list[ProbeRequirement] = []
    for req in reqs:
        count = max(req.duplicate_probe_count, 1)
        for _ in range(count):
            result.append(req)
    return result


def _next_tp_ref(board: Board | None) -> int:
    if board is None:
        return 1
    max_n = 0
    for fp in board.footprints:
        if fp.ref.startswith("TP") and fp.ref[2:].isdigit():
            max_n = max(max_n, int(fp.ref[2:]))
    return max_n + 1


def _next_prot_ref(board: Board | None) -> int:
    if board is None:
        return 1
    max_n = 0
    for fp in board.footprints:
        for prefix in ("R", "FB"):
            if fp.ref.startswith(prefix) and fp.ref[len(prefix):].isdigit():
                max_n = max(max_n, int(fp.ref[len(prefix):]))
    return max_n + 1


def _find_sch_placement(
    sch: Schematic, req: ProbeRequirement, cfg: ProjectConfig,
) -> tuple[float, float]:
    for lb in sch.labels:
        if lb["name"] == req.net_name:
            return lb["x"] + 5.08, lb["y"]
    y_base = 20.0 + len(sch.components) * 5.08
    return 40.0, y_base
