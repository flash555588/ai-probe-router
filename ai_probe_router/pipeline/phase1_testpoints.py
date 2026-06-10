"""Phase 1: testpoint generation, protection circuits, fiducials, tooling."""

from __future__ import annotations

from ..ai.net_classifier import classify_net_detailed
from ..config import ProjectConfig
from ..eda_adapters.kicad.pcb_writer import (
    add_fiducial_footprint,
    add_keepout_zone,
    add_protection_footprint,
    add_testpoint_footprint,
    add_tooling_hole_footprint,
)
from ..eda_adapters.kicad.sch_writer import (
    add_protected_testpoint_symbol,
    add_testpoint_symbol,
)
from ..models.board import Board, Schematic
from ..models.net import NetRole
from ..models.probe import ProbeRequirement, ProbeStyle
from ..solvers.grid_router import RouteResult
from ..solvers.placement_solver import find_placement, place_pogo_array
from ..verification.report import CoverageReport, NetCoverage
from .testpoint_support import (
    add_route_if_clear,
    effective_clearance,
    effective_trace_width,
    find_protection_placement,
    nearest_pad_position,
    net_class_for_role,
    protected_probe_distance_mm,
    trace_length,
)


def run_phase1(
    cfg: ProjectConfig,
    board: Board | None,
    sch: Schematic | None,
) -> CoverageReport:
    report = CoverageReport(total_nets_requested=len(cfg.nets_to_expose))
    tp_counter = _next_tp_ref(board)
    prot_counter = _next_prot_ref(board)
    placed_probes: list[tuple[float, float]] = []
    placed_probe_nets: dict[str, tuple[float, float]] = {}

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
        route_width, route_clearance = net_class_for_role(role, req.current_ma)
        route_width = effective_trace_width(route_width, cfg)
        route_clearance = effective_clearance(route_clearance, cfg)
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
                        protected_probe_distance_mm(protection)
                        if protection is not None else 0.0
                    )
                    placement = find_placement(
                        board, req, cfg.probe, cfg.constraints,
                        placed_probes,
                        index=i,
                        min_target_distance_mm=min_target_distance,
                        role=role, sub_roles=sub_roles,
                        existing_probe_nets=placed_probe_nets,
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
                    source_pos = nearest_pad_position(board, req.net_name, x, y)
                    prot_x, prot_y, prot_rot = find_protection_placement(
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
                        route_results.append(add_route_if_clear(
                            board, req.net_name, source_pos,
                            (prot_fp.pads[0].x, prot_fp.pads[0].y),
                            route_width, route_clearance, cfg.probe.side,
                        ))
                        route_results.append(add_route_if_clear(
                            board, probe_net,
                            (prot_fp.pads[1].x, prot_fp.pads[1].y),
                            (x, y), route_width, route_clearance, cfg.probe.side,
                        ))
                    else:
                        route_results.append(RouteResult(False, [], "no_source_pad"))
                else:
                    source_pos = nearest_pad_position(board, req.net_name, x, y)
                    add_testpoint_footprint(
                        board, req.net_name, x, y,
                        ref=tp_ref, pad_diameter=cfg.probe.pad_diameter_mm,
                        side=cfg.probe.side,
                    )
                    if source_pos is not None:
                        route_results.append(add_route_if_clear(
                            board, req.net_name, source_pos,
                            (x, y), route_width, route_clearance, cfg.probe.side,
                        ))
                    else:
                        route_results.append(RouteResult(False, [], "no_source_pad"))

                placed_probes.append((x, y))
                placed_probe_nets[req.net_name] = (x, y)
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

        trace_w, clearance = net_class_for_role(role, req.current_ma)
        trace_w = effective_trace_width(trace_w, cfg)
        routed = sum(1 for result in route_results if result.ok)
        total_routes = len(route_results)
        # Sum trace lengths from all successful routes
        total_trace_length = sum(
            trace_length(result.points)
            for result in route_results if result.ok
        )
        total_route_bends = sum(
            result.bend_count
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
            route_bends=total_route_bends,
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
        place_fiducials_and_tooling(board, cfg)
        total_routes = report.routed_connections + report.unrouted_connections
        report.routing_ok = report.unrouted_connections == 0 if total_routes else None

    return report


def place_fiducials_and_tooling(board: Board, cfg: ProjectConfig) -> None:
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
