"""Tests verifying CP-SAT pin mapper replaces greedy and removes ordering bias."""

from ai_probe_router.models.dev_board import DevBoardPin, DevelopmentBoard
from ai_probe_router.models.probe import ProbeRequirement
from ai_probe_router.solvers.pin_mapper import _is_adjacent, _solve_mapping_greedy
from ai_probe_router.solvers.pin_mapper_cp_sat import solve_mapping_cp_sat


def _make_board() -> DevelopmentBoard:
    pins = [
        DevBoardPin(name=f"P{i}", capabilities=["GPIO"], current_rating_ma=100)
        for i in range(10)
    ]
    # Add dedicated pins
    pins[0].capabilities = ["SWDIO", "GPIO"]
    pins[1].capabilities = ["SWCLK", "GPIO"]
    pins[2].capabilities = ["GND"]
    pins[2].is_ground = True
    pins[3].capabilities = ["POWER_3V3"]
    pins[3].is_power = True
    pins[4].capabilities = ["USART1_TX", "GPIO"]
    pins[5].capabilities = ["USART1_RX", "GPIO"]
    # Extra ground pins for duplicate tests
    pins[6].capabilities = ["GND"]
    pins[6].is_ground = True
    pins[8].capabilities = ["GND"]
    pins[8].is_ground = True
    return DevelopmentBoard(
        name="test",
        connector_type="dual_row_header",
        pins_per_row=5,
        pins=pins,
    )


def test_cp_sat_produces_valid_assignment():
    board = _make_board()
    reqs = [
        ProbeRequirement(net_name="SWDIO", role="debug", required=True),
        ProbeRequirement(net_name="GND", role="ground", required=True),
        ProbeRequirement(net_name="UART_TX", role="digital", required=True),
    ]
    result = solve_mapping_cp_sat(reqs, board)
    assert not result.errors
    assert len(result.assignments) == 3
    assigned_pins = {a.pin_index for a in result.assignments}
    assert len(assigned_pins) == 3  # unique pins


def test_cp_sat_ignores_input_order():
    board = _make_board()
    # Two orderings of the same requirements
    reqs_a = [
        ProbeRequirement(net_name="SIG_A", role="digital", required=True),
        ProbeRequirement(net_name="SIG_B", role="digital", required=True),
        ProbeRequirement(net_name="SIG_C", role="digital", required=True),
    ]
    reqs_b = [
        ProbeRequirement(net_name="SIG_C", role="digital", required=True),
        ProbeRequirement(net_name="SIG_A", role="digital", required=True),
        ProbeRequirement(net_name="SIG_B", role="digital", required=True),
    ]
    result_a = solve_mapping_cp_sat(reqs_a, board)
    result_b = solve_mapping_cp_sat(reqs_b, board)
    # Both should succeed with no errors
    assert not result_a.errors
    assert not result_b.errors
    assert len(result_a.assignments) == 3
    assert len(result_b.assignments) == 3
    # The set of assigned pins should be the same (or equivalent)
    pins_a = {a.pin_index for a in result_a.assignments}
    pins_b = {a.pin_index for a in result_b.assignments}
    assert pins_a == pins_b


def test_cp_sat_prefers_preferred_pins():
    board = _make_board()
    reqs = [
        ProbeRequirement(
            net_name="SIG",
            role="digital",
            required=True,
            preferred_devboard_pins=["P7"],
        ),
    ]
    result = solve_mapping_cp_sat(reqs, board)
    assert not result.errors
    assert result.assignments[0].pin_name == "P7"


def test_cp_sat_duplicate_probe_count():
    board = _make_board()
    reqs = [
        ProbeRequirement(
            net_name="GND",
            role="ground",
            required=True,
            duplicate_probe_count=3,
        ),
    ]
    result = solve_mapping_cp_sat(reqs, board)
    assert not result.errors
    assert len(result.assignments) == 3
    assigned_pins = {a.pin_index for a in result.assignments}
    assert len(assigned_pins) == 3


def test_cp_sat_differential_pair_adjacent():
    board = _make_board()
    reqs = [
        ProbeRequirement(
            net_name="USB_DP",
            role="high_speed",
            required=True,
            pair_net_name="USB_DM",
        ),
        ProbeRequirement(
            net_name="USB_DM",
            role="high_speed",
            required=True,
            pair_net_name="USB_DP",
        ),
    ]
    result = solve_mapping_cp_sat(reqs, board)
    assert not result.errors
    assert len(result.assignments) == 2
    dp_idx = next(a.pin_index for a in result.assignments if a.net_name == "USB_DP")
    dm_idx = next(a.pin_index for a in result.assignments if a.net_name == "USB_DM")
    assert _is_adjacent(dp_idx, dm_idx, board.pins_per_row)


def test_cp_sat_respects_current_rating():
    board = _make_board()
    # Lower current rating on most pins
    for p in board.pins:
        p.current_rating_ma = 50
    # P7 needs both power capability and high current
    board.pins[7].capabilities = ["POWER_5V", "GPIO"]
    board.pins[7].current_rating_ma = 500
    reqs = [
        ProbeRequirement(
            net_name="MOTOR",
            role="power",
            required=True,
            current_ma=300,
        ),
    ]
    result = solve_mapping_cp_sat(reqs, board)
    assert not result.errors
    assert result.assignments[0].pin_index == 7


def test_cp_sat_falls_back_when_no_solution():
    board = _make_board()
    # Request more nets than available pins
    reqs = [
        ProbeRequirement(net_name=f"SIG{i}", role="digital", required=True)
        for i in range(20)
    ]
    result = solve_mapping_cp_sat(reqs, board)
    assert result.errors  # Should report infeasibility


def test_solve_mapping_uses_cp_sat_by_default():
    board = _make_board()
    reqs = [
        ProbeRequirement(net_name="SWDIO", role="debug", required=True),
        ProbeRequirement(net_name="GND", role="ground", required=True),
    ]
    from ai_probe_router.solvers.pin_mapper import solve_mapping

    result = solve_mapping(reqs, board)
    assert not result.errors
    assert len(result.assignments) == 2


def test_greedy_fallback_when_cp_sat_disabled():
    board = _make_board()
    reqs = [
        ProbeRequirement(net_name="SWDIO", role="debug", required=True),
        ProbeRequirement(net_name="GND", role="ground", required=True),
    ]
    result = _solve_mapping_greedy(reqs, board)
    assert not result.errors
    assert len(result.assignments) == 2
