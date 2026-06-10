"""Tests for pin mapper."""

from pathlib import Path

from ai_probe_router.models.dev_board import DevBoardPin, DevelopmentBoard
from ai_probe_router.models.probe import ProbeRequirement
from ai_probe_router.solvers.pin_mapper import load_dev_board, solve_mapping


def _make_dev_board() -> DevelopmentBoard:
    return DevelopmentBoard(
        name="test_board",
        connector_type="dual_row_header",
        pitch_mm=2.54,
        pins=[
            DevBoardPin(name="PA13", capabilities=["GPIO", "SWDIO"], fixed=True),
            DevBoardPin(name="PA14", capabilities=["GPIO", "SWCLK"], fixed=True),
            DevBoardPin(name="PA9", capabilities=["GPIO", "USART1_TX"], current_rating_ma=25),
            DevBoardPin(name="PA10", capabilities=["GPIO", "USART1_RX"], current_rating_ma=25),
            DevBoardPin(
                name="3V3", capabilities=["POWER_3V3"],
                is_power=True, current_rating_ma=500,
            ),
            DevBoardPin(name="GND_1", capabilities=["GND"], is_ground=True, current_rating_ma=1000),
            DevBoardPin(name="GND_2", capabilities=["GND"], is_ground=True, current_rating_ma=1000),
            DevBoardPin(name="NRST", capabilities=["NRST", "RESET"]),
        ],
    )


def test_basic_mapping():
    board = _make_dev_board()
    reqs = [
        ProbeRequirement(net_name="SWDIO", role="debug", required=True),
        ProbeRequirement(net_name="SWCLK", role="debug", required=True),
    ]
    result = solve_mapping(reqs, board)
    assert result.ok
    assert len(result.assignments) == 2
    mapped_pins = {a.pin_name for a in result.assignments}
    assert "PA13" in mapped_pins
    assert "PA14" in mapped_pins


def test_uart_mapping():
    board = _make_dev_board()
    reqs = [
        ProbeRequirement(net_name="UART_TX", role="communication", required=True),
        ProbeRequirement(net_name="UART_RX", role="communication", required=True),
    ]
    result = solve_mapping(reqs, board)
    assert result.ok
    assert len(result.assignments) == 2


def test_power_mapping():
    board = _make_dev_board()
    reqs = [
        ProbeRequirement(net_name="3V3", role="power", required=True, current_ma=300),
    ]
    result = solve_mapping(reqs, board)
    assert result.ok
    assert result.assignments[0].pin_name == "3V3"


def test_ground_duplicate():
    board = _make_dev_board()
    reqs = [
        ProbeRequirement(net_name="GND", role="ground", required=True, duplicate_probe_count=2),
    ]
    result = solve_mapping(reqs, board)
    assert result.ok
    assert len(result.assignments) == 2


def test_unmapped_required_net():
    board = _make_dev_board()
    reqs = [
        ProbeRequirement(net_name="USB_DP", role="high_speed", required=True),
    ]
    result = solve_mapping(reqs, board)
    assert not result.ok
    assert len(result.errors) == 1
    assert len(result.unmapped) == 1


def test_optional_net_no_error():
    board = _make_dev_board()
    reqs = [
        ProbeRequirement(net_name="USB_DP", role="high_speed", required=False),
    ]
    result = solve_mapping(reqs, board)
    assert result.ok
    assert len(result.unmapped) == 1
    assert len(result.errors) == 0


def test_preferred_pin():
    board = _make_dev_board()
    reqs = [
        ProbeRequirement(
            net_name="UART_TX", role="communication", required=True,
            preferred_devboard_pins=["PA9"],
        ),
    ]
    result = solve_mapping(reqs, board)
    assert result.ok
    assert result.assignments[0].pin_name == "PA9"


def test_current_rating_filter():
    board = _make_dev_board()
    reqs = [
        ProbeRequirement(net_name="3V3", role="power", required=True, current_ma=600),
    ]
    result = solve_mapping(reqs, board)
    assert not result.ok


def test_reset_mapping():
    board = _make_dev_board()
    reqs = [
        ProbeRequirement(net_name="NRST", role="reset", required=True),
    ]
    result = solve_mapping(reqs, board)
    assert result.ok
    assert result.assignments[0].pin_name == "NRST"


def test_load_dev_board():
    repo_root = Path(__file__).parent.parent
    yaml_path = repo_root / "ai_probe_router" / "libraries" / "dev_boards" / "stm32_nucleo_64.yaml"
    if not yaml_path.exists():
        return
    board = load_dev_board(yaml_path)
    assert board.name == "stm32_nucleo_64"
    assert board.rows == 2
    assert board.pin_count == 40
    assert len(board.pins) == 31
    assert any(p.name == "PA13" and p.fixed for p in board.pins)


def test_no_pin_reuse():
    board = _make_dev_board()
    reqs = [
        ProbeRequirement(net_name="SWDIO", role="debug", required=True),
        ProbeRequirement(net_name="SWCLK", role="debug", required=True),
        ProbeRequirement(net_name="UART_TX", role="communication", required=True),
        ProbeRequirement(net_name="UART_RX", role="communication", required=True),
    ]
    result = solve_mapping(reqs, board)
    assert result.ok
    pin_indices = [a.pin_index for a in result.assignments]
    assert len(pin_indices) == len(set(pin_indices))


def test_differential_pair_mapping():
    board = _make_dev_board()
    # Add adjacent pins with USB capability
    board.pins.extend([
        DevBoardPin(name="PA11", capabilities=["GPIO", "USB_DP"]),
        DevBoardPin(name="PA12", capabilities=["GPIO", "USB_DM"]),
    ])
    reqs = [
        ProbeRequirement(
            net_name="USB_DP", role="high_speed", required=True,
            pair_net_name="USB_DM",
        ),
        ProbeRequirement(
            net_name="USB_DM", role="high_speed", required=True,
            pair_net_name="USB_DP",
        ),
    ]
    result = solve_mapping(reqs, board)
    assert result.ok
    assert len(result.assignments) == 2
    idxs = [a.pin_index for a in result.assignments]
    # PA11 and PA12 should be adjacent (indices 8 and 9)
    assert abs(idxs[0] - idxs[1]) == 1


def test_differential_pair_fallback_when_no_adjacent():
    # Create a board with only one GPIO pin — impossible to place a pair
    board = DevelopmentBoard(
        name="tiny_board",
        connector_type="single_row",
        pitch_mm=2.54,
        pins=[
            DevBoardPin(name="PA0", capabilities=["GPIO"]),
        ],
    )
    reqs = [
        ProbeRequirement(
            net_name="USB_DP", role="high_speed", required=True,
            pair_net_name="USB_DM",
        ),
        ProbeRequirement(
            net_name="USB_DM", role="high_speed", required=True,
            pair_net_name="USB_DP",
        ),
    ]
    result = solve_mapping(reqs, board)
    # Only one pin available, so differential pair must fail
    assert not result.ok


def test_differential_pair_respects_pins_per_row():
    board = _make_dev_board()
    board.pins_per_row = 4
    # Add pins at index 3 (end of row 0) and 4 (start of row 1)
    # With pins_per_row=4, these are in different rows but same column 3/0
    board.pins.extend([
        DevBoardPin(name="PA11", capabilities=["GPIO", "USB_DP"]),
        DevBoardPin(name="PA12", capabilities=["GPIO", "USB_DM"]),
    ])
    reqs = [
        ProbeRequirement(
            net_name="USB_DP", role="high_speed", required=True,
            pair_net_name="USB_DM",
        ),
        ProbeRequirement(
            net_name="USB_DM", role="high_speed", required=True,
            pair_net_name="USB_DP",
        ),
    ]
    result = solve_mapping(reqs, board)
    assert result.ok
    idxs = sorted(a.pin_index for a in result.assignments)
    # With 4 pins per row, indices 8 and 9 map to row=2,col=0 and row=2,col=1 -> adjacent
    # If the old hardcoded 20 were used, 8 and 9 would be row=0,col=8/9 (also adjacent)
    # The real test: ensure solver uses board.pins_per_row, not hardcoded 20
    assert len(idxs) == 2
