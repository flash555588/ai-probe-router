"""MCU-specific profile: strapping pins, ADC channels, reserved GPIOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class StrappingPin:
    gpio: str
    function: str
    default_state: str = "floating"
    notes: str = ""


@dataclass
class AdcChannel:
    gpio: str
    adc_unit: int
    channel: int


@dataclass
class McuProfile:
    name: str
    family: str
    strapping_pins: list[StrappingPin] = field(default_factory=list)
    adc_channels: list[AdcChannel] = field(default_factory=list)
    reserved_gpios: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def is_adc_capable(self, gpio: str) -> bool:
        normalized = gpio.upper()
        return any(ch.gpio.upper() == normalized for ch in self.adc_channels)

    def is_strapping_pin(self, gpio: str) -> bool:
        normalized = gpio.upper()
        return any(sp.gpio.upper() == normalized for sp in self.strapping_pins)

    def get_strapping_info(self, gpio: str) -> StrappingPin | None:
        normalized = gpio.upper()
        for sp in self.strapping_pins:
            if sp.gpio.upper() == normalized:
                return sp
        return None

    def is_reserved(self, gpio: str) -> bool:
        normalized = gpio.upper()
        return any(g.upper() == normalized for g in self.reserved_gpios)


def load_mcu_profile(path: str | Path) -> McuProfile:
    text = Path(path).read_text(encoding="utf-8")
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ValueError("MCU profile must be a YAML mapping")
    mcu = raw.get("mcu", raw)

    strapping = [
        StrappingPin(
            gpio=sp["gpio"],
            function=sp.get("function", ""),
            default_state=sp.get("default_state", "floating"),
            notes=sp.get("notes", ""),
        )
        for sp in mcu.get("strapping_pins", [])
    ]

    adc = [
        AdcChannel(
            gpio=ch["gpio"],
            adc_unit=ch.get("adc_unit", 1),
            channel=ch.get("channel", 0),
        )
        for ch in mcu.get("adc_channels", [])
    ]

    return McuProfile(
        name=mcu.get("name", "unknown"),
        family=mcu.get("family", "unknown"),
        strapping_pins=strapping,
        adc_channels=adc,
        reserved_gpios=mcu.get("reserved_gpios", []),
        notes=mcu.get("notes", []),
    )
