"""Core engine: orchestrates Phase 1 (testpoints) and Phase 2 (pin mapping)."""

from __future__ import annotations

import math
from pathlib import Path

from .ai.design_review import run_design_review
from .ai.net_classifier import classify_net, classify_net_detailed
from .ai.rule_generator import generate_rules
from .config import ProjectConfig
from .eda_adapters.kicad.cli_runner import (
    export_drill,
    export_gerbers,
    export_pos,
    run_drc,
    run_erc,
)
from .eda_adapters.kicad.pcb_parser import parse_pcb
from .eda_adapters.kicad.pcb_writer import (
    add_connector_footprint,
    add_fiducial_footprint,
    add_keepout_zone,
    add_net_class,
    add_protection_footprint,
    add_testpoint_footprint,
    add_tooling_hole_footprint,
    add_track_segment,
    write_pcb,
)
from .eda_adapters.kicad.sch_parser import parse_schematic
from .eda_adapters.kicad.sch_writer import (
    add_connector_symbol,
    add_protected_testpoint_symbol,
    add_testpoint_symbol,
    write_schematic,
)
from .models.board import Board, Schematic, _pad_bounds
from .models.dev_board import DevelopmentBoard
from .models.net import NetRole
from .models.probe import ProbeRequirement, ProbeStyle
from .routing.dsn_export import export_dsn
from .routing.freerouting_bridge import route_board as run_freerouting_route
from .routing.module_corridor import analyze_routing_feasibility
from .solvers.constraint_checker import validate_all_probes
from .solvers.grid_router import RouteResult, route_grid
from .solvers.module_graph import build_module_graph
from .solvers.module_placement import plan_module_placement
from .solvers.module_selector import select_modules
from .solvers.pin_mapper import solve_mapping
from .solvers.placement_solver import find_placement, place_pogo_array
from .synthesis.module_instantiator import instantiate_module_sheets
from .verification.bom_report import BomReport
from .verification.bus_report import BusReport
from .verification.manufacturing_report import generate_manufacturing_report
from .verification.module_compatibility_report import (
    ModuleCompatibilityReport,
    analyze_module_compatibility,
)
from .verification.module_graph_report import ModuleGraphReport
from .verification.module_instantiation_report import ModuleInstantiationReport
from .verification.module_placement_report import ModulePlacementReport
from .verification.module_report import ModuleReport
from .verification.pin_report import PinMapReport
from .verification.power_report import PowerReport
from .verification.report import CoverageReport, NetCoverage
from .verification.routing_feasibility_report import RoutingFeasibilityReport
from .verification.diff_pair_skew_report import generate_diff_pair_skew_report


def run(cfg: ProjectConfig, project_dir: str | Path) -> tuple[CoverageReport, PinMapReport | None]:
    base = Path(project_dir)
    sch_path = base / cfg.schematic_file
    pcb_path = base / cfg.board_file

    board: Board | None = None
    sch: Schematic | None = None

    if cfg.board_file and pcb_path.is_file():
        board = parse_pcb(pcb_path)
    if cfg.schematic_file and sch_path.is_file():
        sch = parse_schematic(sch_path)

    module_selection = None
    module_graph_result = None
    module_placement_result = None
    routing_feasibility = None
    module_instantiation_result = None
    module_compatibility_result = None
    if cfg.functional_modules:
        module_selection = select_modules(cfg.functional_modules)
        module_graph_result = build_module_graph(cfg, module_selection, board)
        module_compatibility_result = analyze_module_compatibility(module_graph_result)
        module_placement_result = plan_module_placement(module_graph_result.graph, board)
        routing_feasibility = analyze_routing_feasibility(
            board, module_graph_result.graph, cfg.routing_strategy,
        )

    pin_report: PinMapReport | None = None
    if cfg.development_board is not None and cfg.nets_to_expose:
        pin_report = _run_phase2(cfg, board, sch, cfg.development_board)

    coverage = _run_phase1(cfg, board, sch)

    out_dir = base / "output"
    out_dir.mkdir(exist_ok=True)

    if module_graph_result is not None:
        module_instantiation_result = instantiate_module_sheets(
            sch,
            module_graph_result.graph,
            out_dir,
        )

    if board is not None:
        # Run constraint validation on placed probes
        probe_data = [
            (fp.pads[0].x, fp.pads[0].y, fp.pads[0].net_name)
            for fp in board.footprints
            if fp.ref.startswith("TP") and fp.pads
        ]
        if probe_data:
            validation = validate_all_probes(
                probe_data, board, cfg.constraints, cfg.probe,
            )
            coverage.constraint_violations = len(validation.violations)
            coverage.constraint_ok = validation.ok
            coverage.constraint_messages = [v.message for v in validation.violations]

        # Write net classes from generated rules
        net_names = [e.net_name for e in coverage.entries]
        roles = {n: classify_net(n) for n in net_names}
        sub_roles_map = {
            n: classify_net_detailed(n, cfg.mcu_profile)[1]
            for n in net_names
        }
        rules = generate_rules(roles, cfg.nets_to_expose, net_sub_roles=sub_roles_map)
        for r in rules.net_rules:
            dp_width = r.trace_width_mm if r.differential_pair else None
            dp_gap = 0.15 if r.differential_pair else None
            # Apply impedance control if configured for this net's differential pair
            if r.differential_pair and cfg.impedance_control.has_rules():
                # Match by net name prefix or role
                for rule_name, rule in cfg.impedance_control.rules.items():
                    if rule_name.lower() in r.net_name.lower():
                        dp_width = rule.diff_pair_width_mm
                        dp_gap = rule.diff_pair_gap_mm
                        break
            add_net_class(
                board,
                name=f"NET_{r.net_name}",
                description=r.role.name.lower(),
                clearance=r.clearance_mm,
                trace_width=r.trace_width_mm,
                diff_pair_width=dp_width,
                diff_pair_gap=dp_gap,
            )

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
    if module_selection is not None:
        ModuleReport(module_selection).write(out_dir / "module_report.txt")
    if module_graph_result is not None:
        ModuleGraphReport(module_graph_result).write(out_dir / "module_graph_report.txt")
        BusReport(module_graph_result).write(out_dir / "bus_report.txt")
        PowerReport(module_graph_result).write(out_dir / "power_report.txt")
        BomReport(module_graph_result).write(out_dir / "bom_report.csv")
    if module_compatibility_result is not None:
        ModuleCompatibilityReport(module_compatibility_result).write(
            out_dir / "module_compatibility_report.txt",
        )
    if module_placement_result is not None:
        ModulePlacementReport(module_placement_result).write(
            out_dir / "module_placement_report.txt",
        )
    if module_instantiation_result is not None:
        ModuleInstantiationReport(module_instantiation_result).write(
            out_dir / "module_instantiation_report.txt",
        )
    if routing_feasibility is not None:
        RoutingFeasibilityReport(routing_feasibility).write(
            out_dir / "routing_feasibility_report.txt",
        )
    if pin_report is not None:
        pin_report.write(out_dir / "pin_mapping_report.txt")

    mfg_report = generate_manufacturing_report(board, coverage)
    mfg_report.write(out_dir / "manufacturing_report.txt")
    # Diff pair skew report
    dp_report = generate_diff_pair_skew_report(coverage, cfg.nets_to_expose)
    dp_report.write(out_dir / "diff_pair_skew_report.txt")
    if not dp_report.ok() and dp_report.pairs:
        coverage.notes.append(
            f"Diff pair skew: {sum(1 for p in dp_report.pairs if not p.ok)} pair(s) exceed threshold"
        )

    # Run design review if schematic is available
    if sch is not None:
        review = run_design_review(sch, board, cfg.mcu_profile)
        if review.findings:
            review_path = out_dir / "design_review_report.txt"
            review_path.write_text(review.summary(), encoding="utf-8")
            coverage.notes.append(
                f"Design review: {review.error_count} errors, "
                f"{review.warning_count} warnings"
            )

    if board is not None:
        dsn_path = out_dir / "routing.dsn"
        export_dsn(board, dsn_path)
        route_result = run_freerouting_route(board, dsn_path, out_dir, timeout_sec=60)
        if route_result.ok:
            coverage.notes.append(
                f"Auto-routed in {route_result.duration_sec:.1f}s"
            )
        else:
            coverage.notes.append(
                f"Auto-route skipped: {route_result.error}"
            )

    # Thermal analysis export (placeholder)
    if cfg.thermal_analysis.enabled and board is not None:
        thermal_path = out_dir / f"thermal_simulation.{cfg.thermal_analysis.output_format}"
        lines = ["ref,x,y,net_name,role,current_ma"]
        for fp in board.footprints:
            if not fp.pads:
                continue
            pad = fp.pads[0]
            current = 0.0
            role_str = ""
            for req in cfg.nets_to_expose:
                if req.net_name == pad.net_name:
                    current = req.current_ma
                    role_str = req.role
                    break
            lines.append(f'{fp.ref},{pad.x:.2f},{pad.y:.2f},{pad.net_name},{role_str},{current}')
        thermal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        coverage.notes.append(
            f"Thermal simulation export: {thermal_path.name}"
        )

    # Manufacturing exports (Gerber, Drill, Pick&Place)
    mfg_dir = out_dir / "manufacturing"
    mfg_dir.mkdir(exist_ok=True)
    out_pcb_for_export = out_dir / pcb_path.name
    if out_pcb_for_export.exists():
        gerber_result = export_gerbers(out_pcb_for_export, mfg_dir)
        if gerber_result.ok:
            coverage.notes.append("Gerber files exported")
        drill_result = export_drill(out_pcb_for_export, mfg_dir)
        if drill_result.ok:
            coverage.notes.append("Drill files exported")
        pos_file = mfg_dir / "placement.csv"
        pos_result = export_pos(out_pcb_for_export, pos_file)
        if pos_result.ok:
            coverage.notes.append("Pick&Place file exported")

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
        role, sub_roles = classify_net_detailed(req.net_name, cfg.mcu_profile)
        count = max(req.duplicate_probe_count, 1)
        placed = False
        px, py = 0.0, 0.0
        protection = cfg.protection.get_protection(req.role)
        route_width, route_clearance = _net_class_for_role(role, req.current_ma)
        route_width = _effective_trace_width(route_width, cfg)
        route_clearance = _effective_clearance(route_clearance, cfg)
        route_results: list[RouteResult] = []

        for i in range(count):
            tp_ref = f"TP{tp_counter}"
            tp_counter += 1

            if board is not None:
                if is_pogo and pos_index < len(pogo_positions):
                    x, y = pogo_positions[pos_index]
                    pos_index += 1
                else:
                    min_target_distance = (
                        _protected_probe_distance_mm(protection)
                        if protection is not None else 0.0
                    )
                    placement = find_placement(
                        board, req, cfg.probe, cfg.constraints,
                        placed_probes, index=i,
                        min_target_distance_mm=min_target_distance,
                        role=role, sub_roles=sub_roles,
                    )
                    if placement is None:
                        continue
                    x, y = placement
                    pos_index += 1
                px, py = x, y

                if protection is not None:
                    probe_net = f"PROBE_{req.net_name}"
                    prot_ref = f"{protection.ref_prefix}{prot_counter}"
                    prot_counter += 1
                    source_pos = _nearest_pad_position(board, req.net_name, x, y)
                    prot_x, prot_y, prot_rot = _find_protection_placement(
                        board, req.net_name, x, y, protection,
                    )
                    prot_fp = add_protection_footprint(
                        board, req.net_name, probe_net,
                        prot_x, prot_y,
                        protection,
                        ref=prot_ref, side=cfg.probe.side,
                        rotation=prot_rot,
                    )
                    add_testpoint_footprint(
                        board, probe_net, x, y,
                        ref=tp_ref, pad_diameter=cfg.probe.pad_diameter_mm,
                        side=cfg.probe.side,
                    )
                    if source_pos is not None and len(prot_fp.pads) >= 2:
                        route_results.append(_add_route_if_clear(
                            board, req.net_name, source_pos,
                            (prot_fp.pads[0].x, prot_fp.pads[0].y),
                            route_width, route_clearance, cfg.probe.side,
                        ))
                        route_results.append(_add_route_if_clear(
                            board, probe_net,
                            (prot_fp.pads[1].x, prot_fp.pads[1].y),
                            (x, y), route_width, route_clearance, cfg.probe.side,
                        ))
                    else:
                        route_results.append(RouteResult(False, [], "no_source_pad"))
                else:
                    source_pos = _nearest_pad_position(board, req.net_name, x, y)
                    add_testpoint_footprint(
                        board, req.net_name, x, y,
                        ref=tp_ref, pad_diameter=cfg.probe.pad_diameter_mm,
                        side=cfg.probe.side,
                    )
                    if source_pos is not None:
                        route_results.append(_add_route_if_clear(
                            board, req.net_name, source_pos,
                            (x, y), route_width, route_clearance, cfg.probe.side,
                        ))
                    else:
                        route_results.append(RouteResult(False, [], "no_source_pad"))

                placed_probes.append((x, y))
                placed = True

                # Add keepout zone around probe pad
                keepout_margin = 1.0
                keepout_size = cfg.probe.pad_diameter_mm + keepout_margin * 2
                add_keepout_zone(
                    board, x, y, keepout_size, keepout_size,
                )

            if sch is not None:
                sx, sy = _find_sch_placement(sch, req, cfg)
                # Offset duplicate schematic symbols vertically to avoid overlap
                sy += i * 5.08
                if protection is not None:
                    prot_sch_ref = f"{protection.ref_prefix}{prot_counter - 1}"
                    add_protected_testpoint_symbol(
                        sch, req.net_name, sx, sy,
                        protection,
                        tp_ref=tp_ref, prot_ref=prot_sch_ref,
                        role=role.name.lower(),
                        required=req.required,
                        current_ma=req.current_ma,
                        side=cfg.probe.side,
                    )
                else:
                    add_testpoint_symbol(
                        sch, req.net_name, sx, sy, ref=tp_ref,
                        role=role.name.lower(),
                        required=req.required,
                        current_ma=req.current_ma,
                        side=cfg.probe.side,
                    )

        review_needed = role in {
            NetRole.HIGH_SPEED, NetRole.CLOCK, NetRole.ANALOG,
        } or req.current_ma > 500

        trace_w, clearance = _net_class_for_role(role, req.current_ma)
        trace_w = _effective_trace_width(trace_w, cfg)
        routed = sum(1 for result in route_results if result.ok)
        total_routes = len(route_results)
        # Sum trace lengths from all successful routes
        total_trace_length = sum(
            _trace_length(result.points)
            for result in route_results if result.ok
        )
        if not placed:
            route_status = "not_placed"
        elif total_routes == 0:
            route_status = "not_attempted"
        elif routed == total_routes:
            route_status = "routed"
        elif routed == 0:
            route_status = "unrouted"
        else:
            route_status = "partial"
        route_notes = [
            result.reason for result in route_results
            if not result.ok and result.reason
        ]

        report.entries.append(NetCoverage(
            net_name=req.net_name, role=role, required=req.required,
            has_testpoint=placed, probe_x=px, probe_y=py, side=cfg.probe.side,
            review_required=review_needed,
            trace_width_mm=trace_w,
            clearance_mm=clearance,
            route_status=route_status,
            routed_connections=routed,
            total_connections=total_routes,
            trace_length_mm=round(total_trace_length, 3),
            routing_notes=route_notes,
        ))
        report.routed_connections += routed
        report.unrouted_connections += max(total_routes - routed, 0)
        report.routing_messages.extend(
            f"{req.net_name}: {reason}" for reason in route_notes
        )
        if placed:
            report.covered += 1
        else:
            report.missing += 1

    if board is not None:
        _place_fiducials_and_tooling(board, cfg)
        total_routes = report.routed_connections + report.unrouted_connections
        report.routing_ok = report.unrouted_connections == 0 if total_routes else None

    return report


def _place_fiducials_and_tooling(board: Board, cfg: ProjectConfig) -> None:
    bounds = board.board_bounds()
    if bounds is None:
        return

    edge = cfg.constraints.placement.min_distance_from_board_edge_mm
    fid_offset = max(edge, 3.0)

    if cfg.probe.require_fiducials:
        # Clamp offset so positions stay inside the board and don't cross
        clamped_fid = min(fid_offset, bounds.width / 4, bounds.height / 4)
        # Three fiducials: bottom-left, bottom-right, top-left
        fid_positions = [
            (bounds.min_x + clamped_fid, bounds.min_y + clamped_fid),
            (bounds.max_x - clamped_fid, bounds.min_y + clamped_fid),
            (bounds.min_x + clamped_fid, bounds.max_y - clamped_fid),
        ]
        for i, (fx, fy) in enumerate(fid_positions, start=1):
            add_fiducial_footprint(board, fx, fy, ref=f"FID{i}")

    if cfg.probe.require_tooling_holes:
        th_offset = max(edge, 5.0)
        clamped_th = min(th_offset, bounds.width / 4, bounds.height / 4)
        # Two tooling holes along bottom edge, spaced from corners
        th_positions = [
            (bounds.min_x + clamped_th, bounds.min_y + clamped_th),
            (bounds.max_x - clamped_th, bounds.min_y + clamped_th),
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

    if cfg.probe.style != ProbeStyle.CONNECTOR:
        return pin_report

    if result.assignments:
        rows = dev_board.rows
        pins_per_row = dev_board.pins_per_row
        if sch is not None:
            add_connector_symbol(
                sch, result.assignments,
                ref="J1",
                x=80.0, y=50.0,
                rows=rows,
                pins_per_row=pins_per_row,
            )
        if board is not None:
            bounds = board.board_bounds()
            if bounds:
                # Place connector to the right of the board, aligned vertically
                conn_w = pins_per_row * dev_board.pitch_mm
                conn_h = rows * dev_board.pitch_mm
                margin = 5.0
                cx = bounds.max_x + margin
                cy = (bounds.min_y + bounds.max_y) / 2 - conn_h / 2
            else:
                conn_w = pins_per_row * dev_board.pitch_mm
                conn_h = rows * dev_board.pitch_mm
                cx, cy = 150.0, 100.0
            add_connector_footprint(
                board, result.assignments,
                ref="J1",
                x=cx, y=cy,
                rows=rows,
                pins_per_row=pins_per_row,
                pitch=dev_board.pitch_mm,
                side=cfg.probe.side,
            )
            # Keepout around connector
            add_keepout_zone(
                board, cx + conn_w / 2, cy + conn_h / 2,
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


def _protected_probe_distance_mm(protection) -> float:
    package_room = {
        "0402": 4.0,
        "0603": 4.5,
        "0805": 5.0,
    }
    return package_room.get(protection.package, 4.0)


def _effective_trace_width(width: float, cfg: ProjectConfig) -> float:
    return max(width, cfg.constraints.manufacturing.min_trace_width_mm, 0.20)


def _effective_clearance(clearance: float, cfg: ProjectConfig) -> float:
    return max(
        clearance,
        cfg.constraints.manufacturing.min_clearance_mm,
        cfg.constraints.routing.min_clearance_mm,
        0.20,
    )

def _trace_length(points: list[tuple[float, float]]) -> float:
    """Compute total Euclidean length of a polyline."""
    if len(points) < 2:
        return 0.0
    return sum(
        math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1])
        for i in range(1, len(points))
    )


def _find_protection_placement(
    board: Board,
    net_name: str,
    probe_x: float,
    probe_y: float,
    protection,
) -> tuple[float, float, float]:
    target = _nearest_pad_position(board, net_name, probe_x, probe_y)
    if target is None:
        return probe_x - 2.0, probe_y, 0.0

    tx, ty = target
    dx = probe_x - tx
    dy = probe_y - ty
    dist = math.hypot(dx, dy)
    if dist < 1e-9:
        return probe_x - 2.0, probe_y, 0.0

    # Candidate at midpoint
    cx = (tx + probe_x) / 2
    cy = (ty + probe_y) / 2
    rot = math.degrees(math.atan2(dy, dx))

    # Build occupied zones from all existing pads except current net source
    occupied: list[BoundingBox] = []
    for fp in board.footprints:
        for pad in fp.pads:
            if pad.net_name == net_name:
                continue
            bb = _pad_bounds(pad)
            occupied.append(bb)

    fp_half = {"0402": 0.7, "0603": 1.0, "0805": 1.3, "SOT-23-6": 1.8}.get(protection.package, 1.0)
    margin = 2.0

    for frac in [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95]:
        cx = tx + dx * frac
        cy = ty + dy * frac
        # Footprint bbox at this candidate
        f_min_x = cx - fp_half
        f_max_x = cx + fp_half
        f_min_y = cy - fp_half
        f_max_y = cy + fp_half
        clear = True
        for bb in occupied:
            if f_min_x - margin <= bb.max_x and f_max_x + margin >= bb.min_x and f_min_y - margin <= bb.max_y and f_max_y + margin >= bb.min_y:
                clear = False
                break
        if clear:
            return cx, cy, rot

    # Fallback
    return tx + dx * 0.95, ty + dy * 0.95, rot


def _nearest_pad_position(
    board: Board,
    net_name: str,
    x: float,
    y: float,
) -> tuple[float, float] | None:
    pads = board.find_pads_by_net(net_name)
    if not pads:
        return None
    _fp, pad = min(
        pads,
        key=lambda item: math.hypot(x - item[1].x, y - item[1].y),
    )
    return pad.x, pad.y


def _add_route_if_clear(
    board: Board,
    net_name: str,
    start: tuple[float, float],
    end: tuple[float, float],
    width: float,
    clearance: float,
    side: str,
) -> RouteResult:
    if start == end:
        return RouteResult(True, [start, end])
    result = route_grid(
        board, net_name, start, end,
        width=width, clearance=clearance, side=side,
    )
    if not result.ok:
        return result
    for a, b in zip(result.points, result.points[1:]):
        add_track_segment(
            board, net_name,
            a[0], a[1], b[0], b[1],
            width=width,
            side=side,
        )
    return result


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
