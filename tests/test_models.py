"""Tests for data models and net classifier."""

from ai_probe_router.ai.net_classifier import classify_net
from ai_probe_router.config import load_config
from ai_probe_router.models.board import Board, Footprint, Pad
from ai_probe_router.models.net import NetRole


def test_classify_power():
    assert classify_net("3V3") == NetRole.POWER
    assert classify_net("5V") == NetRole.POWER
    assert classify_net("VCC") == NetRole.POWER
    assert classify_net("VBUS") == NetRole.POWER


def test_classify_ground():
    assert classify_net("GND") == NetRole.GROUND
    assert classify_net("AGND") == NetRole.GROUND


def test_classify_debug():
    assert classify_net("SWDIO") == NetRole.DEBUG
    assert classify_net("SWCLK") == NetRole.DEBUG


def test_classify_communication():
    assert classify_net("UART_TX") == NetRole.COMMUNICATION
    assert classify_net("I2C_SCL") == NetRole.COMMUNICATION
    assert classify_net("SPI_MOSI") == NetRole.COMMUNICATION


def test_classify_reset():
    assert classify_net("NRST") == NetRole.RESET
    assert classify_net("RESET") == NetRole.RESET


def test_classify_high_speed():
    assert classify_net("USB_DP") == NetRole.HIGH_SPEED


def test_classify_unknown():
    assert classify_net("MY_CUSTOM_NET") == NetRole.UNKNOWN


def test_board_find_pads_by_net():
    pad1 = Pad(number="1", net_name="GND", net_id=1)
    pad2 = Pad(number="2", net_name="3V3", net_id=2)
    fp = Footprint(ref="U1", pads=[pad1, pad2])
    board = Board(footprints=[fp], nets={"GND": 1, "3V3": 2})
    found = board.find_pads_by_net("GND")
    assert len(found) == 1
    assert found[0][1].net_name == "GND"


def test_board_next_net_id():
    board = Board(nets={"GND": 1, "3V3": 2, "SWDIO": 5})
    assert board.next_net_id() == 6


def test_load_sample_config(tmp_path):
    import shutil
    from pathlib import Path
    src = Path(__file__).parent.parent / "examples" / "sample_config.yaml"
    dst = tmp_path / "config.yaml"
    shutil.copy(src, dst)
    cfg = load_config(dst)
    assert cfg.eda_tool == "kicad"
    assert len(cfg.nets_to_expose) == 9
    assert cfg.nets_to_expose[0].net_name == "SWDIO"
    assert cfg.probe.pad_diameter_mm == 1.5
