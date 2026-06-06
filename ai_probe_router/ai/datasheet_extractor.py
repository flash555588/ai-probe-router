"""Extract pinout tables from datasheet text/PDF into dev-board YAML.

This is an MVP implementation.  For production use, integrate with a
PDF table extractor (e.g. pdfplumber, camelot) or use an LLM vision
model to read pinout diagrams.

Usage::

    from ai_probe_router.ai.datasheet_extractor import extract_from_text
    pins = extract_from_text(pinout_text)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ExtractedPin:
    name: str
    capabilities: list[str] = field(default_factory=list)
    alternate_functions: list[str] = field(default_factory=list)
    current_rating_ma: float = 25.0
    is_power: bool = False
    is_ground: bool = False
    fixed: bool = False
    notes: str = ""


def extract_from_text(text: str) -> list[ExtractedPin]:
    """Parse a pinout table copied from a PDF datasheet.

    Handles common STM32-style formats::

        PA0  I/O  ADC1_IN0  USART2_CTS  TIM2_CH1  3.6V tolerant
        PA1  I/O  ADC1_IN1  USART2_RTS  TIM2_CH2  3.6V tolerant
        VDD  S    Power supply
        VSS  S    Ground

    Returns a list of ExtractedPin objects.
    """
    pins: list[ExtractedPin] = []
    seen: set[str] = set()

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("Pin", "Name", "—", "-")):
            continue

        parsed = _parse_line(line)
        if parsed and parsed.name not in seen:
            seen.add(parsed.name)
            pins.append(parsed)

    return pins


def _parse_line(line: str) -> ExtractedPin | None:
    """Try to parse a single pinout line."""
    # STM32-style: "PA0  I/O  ADC1_IN0  USART2_CTS  ..."
    parts = [p.strip() for p in line.split() if p.strip()]
    if len(parts) < 2:
        return None

    name = parts[0]
    if not _looks_like_pin(name):
        return None

    pin = ExtractedPin(name=name)

    # Detect power/ground
    if name.upper().startswith(("VDD", "VCC", "VBAT", "VDDA", "VREF")):
        pin.is_power = True
        pin.capabilities.append("power")
    if name.upper().startswith(("VSS", "GND", "DGND", "AGND")):
        pin.is_ground = True
        pin.capabilities.append("ground")

    # Scan remaining parts for capabilities
    for part in parts[1:]:
        up = part.upper()
        if up in ("I/O", "I/O", "INPUT", "OUTPUT", "IN", "OUT", "S"):
            continue  # type column, not a capability
        if up in ("5V", "3.6V", "TOLERANT", "TOLERANT."):
            pin.notes += f" {part}"
            continue
        if _looks_like_af(part):
            pin.alternate_functions.append(part)
            # Derive capabilities from alternate function names
            pin.capabilities.extend(_af_to_caps(part))

    # Deduplicate capabilities
    pin.capabilities = list(dict.fromkeys(pin.capabilities))
    pin.alternate_functions = list(dict.fromkeys(pin.alternate_functions))

    return pin


def _looks_like_pin(name: str) -> bool:
    """Heuristic: does this look like a pin name?"""
    if len(name) < 2:
        return False
    # PA0, PB12, PC7, PD0, PF9, PH0-PH15, VDD, VSS, NRST, BOOT0
    return bool(re.match(r"^(P[A-L]\d+|VDD\d*|VSS\d*|VBAT|VDDA|VREF|NRST|BOOT\d*)$", name, re.I))


def _looks_like_af(text: str) -> bool:
    """Heuristic: does this look like an alternate function?"""
    return bool(re.match(
        r"^(ADC\d*|DAC\d*|USART\d*|UART\d*|SPI\d*|I2C\d*"
        r"|TIM\d*|CAN\d*|ETH|USB|SDIO|FSMC|DCMI|SWD|JTAG).*",
        text, re.I,
    ))


def _af_to_caps(af: str) -> list[str]:
    """Map alternate function name to capability tags."""
    caps: list[str] = []
    up = af.upper()
    if "ADC" in up:
        caps.append("analog")
    if "DAC" in up:
        caps.append("analog")
    if "USART" in up or "UART" in up:
        caps.append("uart")
    if "SPI" in up:
        caps.append("spi")
    if "I2C" in up:
        caps.append("i2c")
    if "TIM" in up:
        caps.append("timer")
    if "CAN" in up:
        caps.append("can")
    if "USB" in up:
        caps.append("usb")
    if "SWD" in up:
        caps.append("swd")
    if "JTAG" in up:
        caps.append("jtag")
    if "ETH" in up:
        caps.append("ethernet")
    return caps


def to_yaml(pins: list[ExtractedPin], board_name: str = "extracted_board") -> str:
    """Serialize extracted pins to dev-board YAML format."""
    data = {
        "name": board_name,
        "connector_type": "dual_row_header",
        "pitch_mm": 2.54,
        "pins": [],
    }
    for p in pins:
        data["pins"].append({
            "name": p.name,
            "capabilities": p.capabilities,
            "alternate_functions": p.alternate_functions,
            "current_rating_ma": p.current_rating_ma,
            "is_power": p.is_power,
            "is_ground": p.is_ground,
            "fixed": p.fixed,
        })
    return yaml.dump(data, sort_keys=False, allow_unicode=True)


def extract_and_save(
    text: str,
    output_path: str | Path,
    board_name: str = "extracted_board",
) -> None:
    """Extract pins from *text* and write YAML to *output_path*."""
    pins = extract_from_text(text)
    yaml_text = to_yaml(pins, board_name)
    Path(output_path).write_text(yaml_text, encoding="utf-8")
