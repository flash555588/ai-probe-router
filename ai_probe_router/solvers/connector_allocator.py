"""Connector pin allocation: reservation table and assignment optimization.

Deterministic rules only. Strategies rearrange existing pin-mapper
assignments without inventing new ones; the reservation pass classifies
every connector pin as probe, power, ground, reserved, or free and emits
readiness diagnostics for conflicts and capacity pressure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace

from ..models.dev_board import DevBoardPin, DevelopmentBoard
from ..models.probe import ProbeRequirement
from ..models.readiness_codes import ReadinessCode
from .pin_mapper import MappingResult, PinAssignment, _role_to_capabilities

_logger = logging.getLogger(__name__)

STRATEGY_MINIMIZE_SPREAD = "minimize_spread"
STRATEGY_GROUP_BY_FUNCTION = "group_by_function"
STRATEGY_NONE = "none"
KNOWN_STRATEGIES = (
    STRATEGY_MINIMIZE_SPREAD,
    STRATEGY_GROUP_BY_FUNCTION,
    STRATEGY_NONE,
)

DEFAULT_NEAR_LIMIT_THRESHOLD = 0.8

_ROLE_PRIORITY = {
    "debug": 0, "reset": 1, "power": 2, "ground": 3,
    "communication": 4, "digital": 5, "analog": 6, "gpio": 7,
}


@dataclass
class ConnectorPinReservation:
    pin_name: str
    pin_index: int
    row: int
    column: int
    status: str
    net_name: str = ""
    role: str = ""
    fixed: bool = False


@dataclass
class ConnectorPinConflict:
    pin_index: int
    pin_name: str
    nets: list[str] = field(default_factory=list)


@dataclass
class ConnectorAllocationResult:
    strategy: str = STRATEGY_NONE
    connector_type: str = ""
    rows: int = 0
    pins_per_row: int = 0
    reservations: list[ConnectorPinReservation] = field(default_factory=list)
    conflicts: list[ConnectorPinConflict] = field(default_factory=list)
    used_pins: int = 0
    free_pins: int = 0
    utilization_percent: float = 0.0
    spread_span: int = 0
    near_limit: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def optimize_connector_assignments(
    mapping: MappingResult,
    board: DevelopmentBoard,
    requirements: list[ProbeRequirement],
    strategy: str,
) -> tuple[list[PinAssignment], list[str]]:
    """Return reordered assignments according to the configured strategy.

    The input mapping is never mutated. Assignments tied to preferred pins,
    fixed pins, or differential pairs are never moved.
    """
    warnings: list[str] = []
    assignments = [replace(a) for a in mapping.assignments]

    if strategy == STRATEGY_NONE or not assignments:
        return assignments, warnings
    if strategy not in KNOWN_STRATEGIES:
        warnings.append(
            f"Unknown connector_allocation_strategy '{strategy}'; "
            "assignments left unchanged"
        )
        return assignments, warnings

    req_by_net = {r.net_name: r for r in requirements}
    immovable = _immovable_nets(assignments, req_by_net, board)

    if strategy == STRATEGY_MINIMIZE_SPREAD:
        _minimize_spread(assignments, board, req_by_net, immovable)
    elif strategy == STRATEGY_GROUP_BY_FUNCTION:
        _group_by_function(assignments, board, req_by_net, immovable)
    return assignments, warnings


def allocate_connector_pins(
    mapping: MappingResult,
    board: DevelopmentBoard,
    requirements: list[ProbeRequirement],
    strategy: str = STRATEGY_NONE,
    near_limit_threshold: float = DEFAULT_NEAR_LIMIT_THRESHOLD,
) -> ConnectorAllocationResult:
    """Build the per-pin reservation table and diagnostics."""
    result = ConnectorAllocationResult(
        strategy=strategy,
        connector_type=board.connector_type,
        rows=board.rows,
        pins_per_row=board.pins_per_row,
    )
    req_by_net = {r.net_name: r for r in requirements}

    by_index: dict[int, list[PinAssignment]] = {}
    for a in mapping.assignments:
        if a.pin_index < 0 or a.pin_index >= len(board.pins):
            result.errors.append(ReadinessCode.CONNECTOR_PIN_CONFLICT)
            result.errors.append(
                f"  pin={a.pin_name} index={a.pin_index} net={a.net_name} "
                "out of connector range"
            )
            continue
        by_index.setdefault(a.pin_index, []).append(a)

    for idx, pin in enumerate(board.pins):
        assigned = by_index.get(idx, [])
        row, col = divmod(idx, board.pins_per_row) if board.pins_per_row else (0, idx)
        if not assigned:
            result.reservations.append(ConnectorPinReservation(
                pin_name=pin.name,
                pin_index=idx,
                row=row,
                column=col,
                status=_unassigned_status(pin),
                fixed=pin.fixed,
            ))
            continue

        if len(assigned) > 1:
            conflict = ConnectorPinConflict(
                pin_index=idx,
                pin_name=pin.name,
                nets=sorted(a.net_name for a in assigned),
            )
            result.conflicts.append(conflict)
            result.errors.append(ReadinessCode.CONNECTOR_PIN_CONFLICT)
            result.errors.append(
                f"  pin={pin.name} index={idx} nets={conflict.nets}"
            )

        primary = assigned[0]
        req = req_by_net.get(primary.net_name)
        role = req.role if req is not None else ""
        if pin.fixed and req is not None and not _capability_ok(pin, req):
            result.errors.append(ReadinessCode.CONNECTOR_RESERVED_PIN_OVERRIDE)
            result.errors.append(
                f"  pin={pin.name} index={idx} net={primary.net_name} "
                f"role={role} lacks capability overlap with fixed pin"
            )
        result.reservations.append(ConnectorPinReservation(
            pin_name=pin.name,
            pin_index=idx,
            row=row,
            column=col,
            status=_assigned_status(role),
            net_name=primary.net_name,
            role=role,
            fixed=pin.fixed,
        ))

    used_indices = sorted(by_index)
    result.used_pins = len(used_indices)
    result.free_pins = sum(
        1 for r in result.reservations if r.status == "free"
    )
    if board.pins:
        result.utilization_percent = round(
            100.0 * result.used_pins / len(board.pins), 1
        )
    if len(used_indices) >= 2:
        result.spread_span = used_indices[-1] - used_indices[0]
    if (
        board.pins
        and result.used_pins / len(board.pins) >= near_limit_threshold
    ):
        result.near_limit = True
        result.warnings.append(ReadinessCode.CONNECTOR_ALLOCATION_NEAR_LIMIT)
        result.warnings.append(
            f"  used={result.used_pins}/{len(board.pins)} pins "
            f"({result.utilization_percent:.0f}%)"
        )

    _logger.info(
        "Connector allocation: %d used, %d free, %d conflicts, span=%d",
        result.used_pins, result.free_pins,
        len(result.conflicts), result.spread_span,
    )
    return result


def _unassigned_status(pin: DevBoardPin) -> str:
    if pin.fixed:
        return "reserved"
    if pin.is_power:
        return "power"
    if pin.is_ground:
        return "ground"
    return "free"


def _assigned_status(role: str) -> str:
    role_lc = role.lower()
    if role_lc in ("power",):
        return "power"
    if role_lc in ("ground", "gnd"):
        return "ground"
    return "probe"


def _capability_ok(pin: DevBoardPin, req: ProbeRequirement) -> bool:
    needed = _role_to_capabilities(req.role, req.net_name, req.pair_net_name)
    pin_caps = set(pin.capabilities) | set(pin.alternate_functions)
    return bool(needed & pin_caps)


def _immovable_nets(
    assignments: list[PinAssignment],
    req_by_net: dict[str, ProbeRequirement],
    board: DevelopmentBoard,
) -> set[str]:
    paired: set[str] = set()
    for req in req_by_net.values():
        if req.pair_net_name:
            paired.add(req.net_name)
            paired.add(req.pair_net_name)

    immovable: set[str] = set(paired)
    for a in assignments:
        req = req_by_net.get(a.net_name)
        if req is None:
            immovable.add(a.net_name)
            continue
        if a.pin_name in req.preferred_devboard_pins:
            immovable.add(a.net_name)
        if 0 <= a.pin_index < len(board.pins) and board.pins[a.pin_index].fixed:
            immovable.add(a.net_name)
    return immovable


def _valid_target(
    pin: DevBoardPin,
    req: ProbeRequirement,
) -> bool:
    if req.current_ma > 0 and pin.current_rating_ma < req.current_ma:
        return False
    return _capability_ok(pin, req)


def _minimize_spread(
    assignments: list[PinAssignment],
    board: DevelopmentBoard,
    req_by_net: dict[str, ProbeRequirement],
    immovable: set[str],
) -> None:
    """Shrink the index span by relocating boundary assignments inward.

    Each accepted move strictly reduces the span, so the loop terminates.
    """
    while True:
        used = {a.pin_index for a in assignments}
        if len(used) < 2:
            return
        lo, hi = min(used), max(used)
        if not _try_move_boundary(
            assignments, board, req_by_net, immovable, used, lo, hi,
        ):
            return


def _try_move_boundary(
    assignments: list[PinAssignment],
    board: DevelopmentBoard,
    req_by_net: dict[str, ProbeRequirement],
    immovable: set[str],
    used: set[int],
    lo: int,
    hi: int,
) -> bool:
    free_inside = [
        i for i in range(lo, hi + 1)
        if i not in used and i < len(board.pins)
    ]
    # Move the highest assignment to the smallest valid free slot inside
    # the span, then symmetrically the lowest to the largest free slot.
    for boundary, candidates in (
        (hi, free_inside),
        (lo, list(reversed(free_inside))),
    ):
        for a in sorted(assignments, key=lambda x: x.net_name):
            if a.pin_index != boundary or a.net_name in immovable:
                continue
            req = req_by_net.get(a.net_name)
            if req is None:
                continue
            for target in candidates:
                if _valid_target(board.pins[target], req):
                    a.pin_index = target
                    a.pin_name = board.pins[target].name
                    return True
    return False


def _group_by_function(
    assignments: list[PinAssignment],
    board: DevelopmentBoard,
    req_by_net: dict[str, ProbeRequirement],
    immovable: set[str],
) -> None:
    """Repack movable assignments in role-priority order onto low indices."""
    movable = [a for a in assignments if a.net_name not in immovable]
    occupied = {a.pin_index for a in assignments}

    def sort_key(a: PinAssignment) -> tuple[int, str, int]:
        req = req_by_net[a.net_name]
        return (_ROLE_PRIORITY.get(req.role, 99), a.net_name, a.pin_index)

    for a in sorted(movable, key=sort_key):
        req = req_by_net[a.net_name]
        occupied.discard(a.pin_index)
        for idx, pin in enumerate(board.pins):
            if idx in occupied:
                continue
            if _valid_target(pin, req):
                a.pin_index = idx
                a.pin_name = pin.name
                break
        occupied.add(a.pin_index)
