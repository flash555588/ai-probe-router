"""Tests for the connector pin allocator and assignment optimizer."""

from __future__ import annotations

from ai_probe_router.models.dev_board import DevBoardPin, DevelopmentBoard
from ai_probe_router.models.probe import ProbeRequirement
from ai_probe_router.models.readiness_codes import ReadinessCode
from ai_probe_router.solvers.connector_allocator import (
    allocate_connector_pins,
    optimize_connector_assignments,
)
from ai_probe_router.solvers.pin_mapper import MappingResult, PinAssignment


def _board(pins: list[DevBoardPin], pins_per_row: int = 10) -> DevelopmentBoard:
    rows = max(1, (len(pins) + pins_per_row - 1) // pins_per_row)
    return DevelopmentBoard(
        name="test_board",
        connector_type="dual_row_header",
        rows=rows,
        pins_per_row=pins_per_row,
        pins=pins,
    )


def _gpio_board(count: int = 20) -> DevelopmentBoard:
    return _board([
        DevBoardPin(name=f"P{i}", capabilities=["GPIO"]) for i in range(count)
    ])


def _mapping(*assignments: tuple[str, int]) -> MappingResult:
    result = MappingResult()
    for net, idx in assignments:
        result.assignments.append(
            PinAssignment(net_name=net, pin_name=f"P{idx}", pin_index=idx)
        )
    return result


# ---------------------------------------------------------------------------
# allocate_connector_pins: reservation classification
# ---------------------------------------------------------------------------

def test_reservation_status_classification():
    board = _board([
        DevBoardPin(name="GND", capabilities=["GND"], is_ground=True),
        DevBoardPin(name="3V3", capabilities=["POWER_3V3"], is_power=True),
        DevBoardPin(name="SWDIO", capabilities=["SWDIO"], fixed=True),
        DevBoardPin(name="PA0", capabilities=["GPIO"]),
        DevBoardPin(name="PA1", capabilities=["GPIO"]),
    ])
    reqs = [
        ProbeRequirement(net_name="GND", role="ground"),
        ProbeRequirement(net_name="LED", role="gpio"),
    ]
    mapping = MappingResult(assignments=[
        PinAssignment(net_name="GND", pin_name="GND", pin_index=0),
        PinAssignment(net_name="LED", pin_name="PA0", pin_index=3),
    ])

    result = allocate_connector_pins(mapping, board, reqs)

    statuses = {r.pin_index: r.status for r in result.reservations}
    assert statuses[0] == "ground"     # assigned ground net
    assert statuses[1] == "power"      # unassigned power pin
    assert statuses[2] == "reserved"   # unassigned fixed pin
    assert statuses[3] == "probe"      # assigned gpio net
    assert statuses[4] == "free"
    assert result.ok
    assert result.used_pins == 2
    assert result.free_pins == 1
    assert result.spread_span == 3


def test_pin_conflict_reported_as_error():
    board = _gpio_board(4)
    reqs = [
        ProbeRequirement(net_name="A", role="gpio"),
        ProbeRequirement(net_name="B", role="gpio"),
    ]
    mapping = _mapping(("A", 1), ("B", 1))

    result = allocate_connector_pins(mapping, board, reqs)

    assert not result.ok
    assert ReadinessCode.CONNECTOR_PIN_CONFLICT in result.errors
    assert len(result.conflicts) == 1
    assert result.conflicts[0].nets == ["A", "B"]


def test_reserved_pin_override_reported():
    board = _board([
        DevBoardPin(name="NRST", capabilities=["NRST"], fixed=True),
        DevBoardPin(name="PA0", capabilities=["GPIO"]),
    ])
    reqs = [ProbeRequirement(net_name="SENSOR", role="analog")]
    mapping = MappingResult(assignments=[
        PinAssignment(net_name="SENSOR", pin_name="NRST", pin_index=0),
    ])

    result = allocate_connector_pins(mapping, board, reqs)

    assert not result.ok
    assert ReadinessCode.CONNECTOR_RESERVED_PIN_OVERRIDE in result.errors


def test_near_limit_warning():
    board = _gpio_board(5)
    reqs = [ProbeRequirement(net_name=f"N{i}", role="gpio") for i in range(4)]
    mapping = _mapping(*((f"N{i}", i) for i in range(4)))

    result = allocate_connector_pins(mapping, board, reqs)

    assert result.ok
    assert result.near_limit
    assert ReadinessCode.CONNECTOR_ALLOCATION_NEAR_LIMIT in result.warnings
    assert result.utilization_percent == 80.0


def test_out_of_range_assignment_is_error():
    board = _gpio_board(2)
    reqs = [ProbeRequirement(net_name="A", role="gpio")]
    mapping = _mapping(("A", 99))

    result = allocate_connector_pins(mapping, board, reqs)

    assert not result.ok
    assert ReadinessCode.CONNECTOR_PIN_CONFLICT in result.errors


def test_empty_mapping_yields_all_free():
    board = _gpio_board(3)
    result = allocate_connector_pins(MappingResult(), board, [])
    assert result.ok
    assert result.used_pins == 0
    assert result.free_pins == 3
    assert result.spread_span == 0
    assert not result.near_limit


# ---------------------------------------------------------------------------
# optimize_connector_assignments
# ---------------------------------------------------------------------------

def test_minimize_spread_shrinks_span():
    board = _gpio_board(20)
    reqs = [
        ProbeRequirement(net_name="A", role="gpio"),
        ProbeRequirement(net_name="B", role="gpio"),
        ProbeRequirement(net_name="C", role="gpio"),
    ]
    mapping = _mapping(("A", 0), ("B", 10), ("C", 19))

    optimized, warnings = optimize_connector_assignments(
        mapping, board, reqs, "minimize_spread",
    )

    assert warnings == []
    indices = sorted(a.pin_index for a in optimized)
    span = indices[-1] - indices[0]
    assert span < 19
    assert len(set(indices)) == 3


def test_minimize_spread_keeps_preferred_and_fixed_pins():
    pins = [DevBoardPin(name=f"P{i}", capabilities=["GPIO"]) for i in range(10)]
    pins[9] = DevBoardPin(name="P9", capabilities=["GPIO"], fixed=True)
    board = _board(pins)
    reqs = [
        ProbeRequirement(net_name="PREF", role="gpio",
                         preferred_devboard_pins=["P0"]),
        ProbeRequirement(net_name="FIX", role="gpio"),
        ProbeRequirement(net_name="MOV", role="gpio"),
    ]
    mapping = _mapping(("PREF", 0), ("FIX", 9), ("MOV", 5))

    optimized, _ = optimize_connector_assignments(
        mapping, board, reqs, "minimize_spread",
    )

    by_net = {a.net_name: a.pin_index for a in optimized}
    assert by_net["PREF"] == 0
    assert by_net["FIX"] == 9


def test_minimize_spread_keeps_differential_pairs():
    board = _gpio_board(20)
    reqs = [
        ProbeRequirement(net_name="USB_DP", role="high_speed",
                         pair_net_name="USB_DM"),
        ProbeRequirement(net_name="USB_DM", role="high_speed",
                         pair_net_name="USB_DP"),
        ProbeRequirement(net_name="X", role="gpio"),
    ]
    mapping = _mapping(("USB_DP", 14), ("USB_DM", 15), ("X", 0))

    optimized, _ = optimize_connector_assignments(
        mapping, board, reqs, "minimize_spread",
    )

    by_net = {a.net_name: a.pin_index for a in optimized}
    assert by_net["USB_DP"] == 14
    assert by_net["USB_DM"] == 15


def test_minimize_spread_respects_capabilities():
    pins = [
        DevBoardPin(name="GND0", capabilities=["GND"]),
        DevBoardPin(name="GND1", capabilities=["GND"]),
        DevBoardPin(name="P2", capabilities=["GPIO"]),
        DevBoardPin(name="P3", capabilities=["GPIO"]),
        DevBoardPin(name="P4", capabilities=["GPIO"]),
    ]
    board = _board(pins)
    reqs = [
        ProbeRequirement(net_name="SIG", role="gpio"),
        ProbeRequirement(net_name="SIG2", role="gpio"),
    ]
    # Span 2..4; free slot 3 is GPIO-valid; slots 0/1 are GND-only.
    mapping = _mapping(("SIG", 2), ("SIG2", 4))

    optimized, _ = optimize_connector_assignments(
        mapping, board, reqs, "minimize_spread",
    )

    indices = {a.pin_index for a in optimized}
    assert indices == {2, 3}


def test_group_by_function_orders_by_role_priority():
    board = _gpio_board(10)
    reqs = [
        ProbeRequirement(net_name="LED", role="gpio"),
        ProbeRequirement(net_name="SWCLK", role="debug"),
        ProbeRequirement(net_name="UART", role="communication"),
    ]
    mapping = _mapping(("LED", 2), ("SWCLK", 7), ("UART", 4))

    optimized, _ = optimize_connector_assignments(
        mapping, board, reqs, "group_by_function",
    )

    by_net = {a.net_name: a.pin_index for a in optimized}
    # debug < communication < gpio
    assert by_net["SWCLK"] < by_net["UART"] < by_net["LED"]
    assert len(set(by_net.values())) == 3


def test_unknown_strategy_warns_and_passes_through():
    board = _gpio_board(5)
    reqs = [ProbeRequirement(net_name="A", role="gpio")]
    mapping = _mapping(("A", 3))

    optimized, warnings = optimize_connector_assignments(
        mapping, board, reqs, "totally_bogus",
    )

    assert len(warnings) == 1
    assert "totally_bogus" in warnings[0]
    assert optimized[0].pin_index == 3


def test_none_strategy_passes_through():
    board = _gpio_board(5)
    mapping = _mapping(("A", 3))
    optimized, warnings = optimize_connector_assignments(
        mapping, board, [ProbeRequirement(net_name="A", role="gpio")], "none",
    )
    assert warnings == []
    assert optimized[0].pin_index == 3


def test_optimizer_does_not_mutate_input():
    board = _gpio_board(20)
    reqs = [
        ProbeRequirement(net_name="A", role="gpio"),
        ProbeRequirement(net_name="B", role="gpio"),
    ]
    mapping = _mapping(("A", 0), ("B", 19))

    optimize_connector_assignments(mapping, board, reqs, "minimize_spread")

    assert [a.pin_index for a in mapping.assignments] == [0, 19]


def test_optimizer_is_deterministic():
    board = _gpio_board(20)
    reqs = [ProbeRequirement(net_name=f"N{i}", role="gpio") for i in range(6)]
    mapping = _mapping(*((f"N{i}", i * 3) for i in range(6)))

    first, _ = optimize_connector_assignments(
        mapping, board, reqs, "minimize_spread",
    )
    second, _ = optimize_connector_assignments(
        mapping, board, reqs, "minimize_spread",
    )

    assert [(a.net_name, a.pin_index) for a in first] == [
        (a.net_name, a.pin_index) for a in second
    ]
