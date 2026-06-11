"""Phase 1: probe placement and escape routing.

Places testpoint/pogo footprints for every requested net, adds protection
components where configured, routes probe escapes with the grid router, and
accumulates per-net coverage into a ``CoverageReport``.
"""

from __future__ import annotations

import math

from ..ai.net_classifier import classify_net_detailed
from ..config import ProjectConfig
from ..eda_adapters.kicad.pcb_writer import (
    add_fiducial_footprint,
    add_keepout_zone,
    add_protection_footprint,
    add_testpoint_footprint,
    add_tooling_hole_footprint,
    add_track_segment,
)
from ..eda_adapters.kicad.sch_writer import (
    add_protected_testpoint_symbol,
    add_testpoint_symbol,
)
from ..models.board import Board, BoundingBox, Schematic, _pad_bounds
from ..models.net import NetRole
from ..models.probe import ProbeRequirement, ProbeStyle
from ..solvers.grid_router import RouteResult, route_grid
from ..solvers.placement_solver import find_placement, place_pogo_array
from ..solvers.placement_solver_global import PlacementTask, solve_placement_global
from ..verification.report import CoverageReport, NetCoverage


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

    # Global placement optimisation (non-pogo, board present)
    global_placements: dict[tuple[str, int], tuple[float, float] | None] = {}
    if board is not None and not is_pogo:
        tasks = []
        for req in cfg.nets_to_expose:
            role, sub_roles = classify_net_detailed(req.net_name, cfg.mcu_profile)
            count = max(req.duplicate_probe_count, 1)
            for i in range(count):
                tasks.append(PlacementTask(req, i, role, sub_roles))
        if tasks:
            global_placements = solve_placement_global(
                board, tasks, cfg.probe, cfg.constraints,
            )

    pos_index = 0
    for req in cfg.nets_to_expose:
        role, sub_roles = classify_net_detailed(req.net_name, cfg.mcu_profile)
        count = max(req.duplicate_probe_count, 1)
        placed = False
        px, py = 0.0, 0.0
        protection = cfg.protection.get_protection(req.role)
        route_width, route_clearance = _net_class_for_role(role, req.current_ma, cfg)
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
                    precomputed = global_placements.get((req.net_name, i))
                    if precomputed is not None:
                        x, y = precomputed
                        pos_index += 1
                    else:
                        min_target_distance = (
                            _protected_probe_distance_mm(protection)
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
        }
        trace_w, clearance = _net_class_for_role(role, req.current_ma, cfg)
        trace_w = _effective_trace_width(trace_w, cfg)
        routed = sum(1 for result in route_results if result.ok)
        total_routes = len(route_results)
        # Sum trace lengths from all successful routes
        total_trace_length = sum(
            _trace_length(result.points)
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


def _net_class_for_role(
    role: NetRole, current_ma: float, cfg: ProjectConfig,
) -> tuple[float, float]:
    rr = cfg.constraints.routing
    mc = cfg.constraints.manufacturing
    min_clearance = max(rr.min_clearance_mm, mc.min_clearance_mm)

    if role == NetRole.POWER:
        width = max(rr.power_trace_width_mm, 0.3)
        if current_ma > 500:
            width = max(width, 0.5)
        return width, min_clearance
    if role == NetRole.GROUND:
        return max(rr.power_trace_width_mm, 0.3), min_clearance
    if role == NetRole.HIGH_SPEED:
        return rr.default_trace_width_mm, max(min_clearance, 0.2)
    if role == NetRole.ANALOG:
        return max(rr.analog_trace_width_mm, 0.2), max(min_clearance, 0.25)
    if role == NetRole.CLOCK:
        return rr.default_trace_width_mm, max(min_clearance, 0.2)
    return rr.default_trace_width_mm, min_clearance


def _protected_probe_distance_mm(protection) -> float:
    package_room = {
        "0402": 4.0,
        "0603": 4.5,
        "0805": 5.0,
    }
    return package_room.get(protection.package, 4.0)


def _effective_trace_width(width: float, cfg: ProjectConfig) -> float:
    return max(width, cfg.constraints.manufacturing.min_trace_width_mm)


def _effective_clearance(clearance: float, cfg: ProjectConfig) -> float:
    return max(
        clearance,
        cfg.constraints.manufacturing.min_clearance_mm,
        cfg.constraints.routing.min_clearance_mm,
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

    fp_half = {
        "0402": 0.7,
        "0603": 1.0,
        "0805": 1.3,
        "SOT-23-6": 1.8,
    }.get(protection.package, 1.0)
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
            overlaps_x = (
                f_min_x - margin <= bb.max_x
                and f_max_x + margin >= bb.min_x
            )
            overlaps_y = (
                f_min_y - margin <= bb.max_y
                and f_max_y + margin >= bb.min_y
            )
            if overlaps_x and overlaps_y:
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
