"""Tests for datasheet extractor MVP."""

from __future__ import annotations

from ai_probe_router.ai.datasheet_extractor import (
    ExtractedPin,
    extract_from_text,
    to_yaml,
)

SAMPLE_PINOUT = """\
Pin Name Type Alternate functions
PA0  I/O  ADC1_IN0  USART2_CTS  TIM2_CH1  3.6V tolerant
PA1  I/O  ADC1_IN1  USART2_RTS  TIM2_CH2  3.6V tolerant
PA13 I/O  SWDIO     JTMS
PA14 I/O  SWCLK     JTCK
VDD  S    Power supply
VSS  S    Ground
NRST I/O  Reset
BOOT0 I   Boot mode selection
"""


def test_extracts_gpio_pins():
    pins = extract_from_text(SAMPLE_PINOUT)
    names = {p.name for p in pins}
    assert "PA0" in names
    assert "PA1" in names
    assert "PA13" in names
    assert "PA14" in names


def test_detects_power_ground():
    pins = extract_from_text(SAMPLE_PINOUT)
    vdd = next(p for p in pins if p.name == "VDD")
    vss = next(p for p in pins if p.name == "VSS")
    assert vdd.is_power
    assert vss.is_ground
    assert "power" in vdd.capabilities
    assert "ground" in vss.capabilities


def test_extracts_alternate_functions():
    pins = extract_from_text(SAMPLE_PINOUT)
    pa0 = next(p for p in pins if p.name == "PA0")
    assert "ADC1_IN0" in pa0.alternate_functions
    assert "USART2_CTS" in pa0.alternate_functions
    assert "analog" in pa0.capabilities
    assert "uart" in pa0.capabilities


def test_detects_swd():
    pins = extract_from_text(SAMPLE_PINOUT)
    pa13 = next(p for p in pins if p.name == "PA13")
    assert "swd" in pa13.capabilities


def test_skips_header_lines():
    pins = extract_from_text("Pin Name Type\nPA0 I/O\n")
    assert len(pins) == 1
    assert pins[0].name == "PA0"


def test_to_yaml_format():
    pins = [ExtractedPin(name="PA0", capabilities=["analog", "uart"])]
    text = to_yaml(pins, board_name="test_board")
    assert "name: test_board" in text
    assert "PA0" in text
    assert "analog" in text
