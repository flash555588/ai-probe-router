"""Reusable chip library models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .interface import InterfaceSpec
from .package import PackageOption
from .power_domain import PowerDomain


@dataclass
class ChipPin:
    name: str
    direction: str = "passive"
    capabilities: list[str] = field(default_factory=list)
    voltage_domain: str = ""


@dataclass
class ChipDefinition:
    mpn: str
    category: str = ""
    description: str = ""
    symbol: str = ""
    package_options: list[PackageOption] = field(default_factory=list)
    power_domains: list[PowerDomain] = field(default_factory=list)
    interfaces: list[InterfaceSpec] = field(default_factory=list)
    pins: list[ChipPin] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    required_passives: list[dict[str, Any]] = field(default_factory=list)


def load_chip_definition(path: str | Path) -> ChipDefinition:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Chip definition must be a YAML mapping: {path}")

    chip = raw.get("chip", {})
    if not isinstance(chip, dict):
        raise ValueError(f"Chip definition missing 'chip' mapping: {path}")

    packages = [
        PackageOption(
            name=str(pkg.get("name", "")),
            footprint=str(pkg.get("footprint", "")),
            area_mm2=float(pkg.get("area_mm2", 0.0)),
        )
        for pkg in raw.get("package_options", [])
        if isinstance(pkg, dict)
    ]
    power_domains = [
        PowerDomain(
            name=str(domain.get("name", "")),
            voltage_min=float(domain.get("voltage_min", 0.0)),
            voltage_max=float(domain.get("voltage_max", 0.0)),
            current_typ_ma=float(domain.get("current_typ_ma", 0.0)),
        )
        for domain in raw.get("power", {}).get("domains", [])
        if isinstance(domain, dict)
    ]
    interfaces = [
        InterfaceSpec(
            type=str(iface.get("type", "")),
            pins=[str(pin) for pin in iface.get("pins", [])],
            address_configurable=bool(iface.get("address_configurable", False)),
            max_bus_speed=str(iface.get("max_bus_speed", "")),
        )
        for iface in raw.get("interfaces", [])
        if isinstance(iface, dict)
    ]
    pins = [
        ChipPin(
            name=str(pin.get("name", "")),
            direction=str(pin.get("direction", "passive")),
            capabilities=[str(cap) for cap in pin.get("capabilities", [])],
            voltage_domain=str(pin.get("voltage_domain", "")),
        )
        for pin in raw.get("pins", [])
        if isinstance(pin, dict)
    ]
    return ChipDefinition(
        mpn=str(chip.get("mpn", "")),
        category=str(chip.get("category", "")),
        description=str(chip.get("description", "")),
        symbol=str(chip.get("symbol", "")),
        package_options=packages,
        power_domains=power_domains,
        interfaces=interfaces,
        pins=pins,
        constraints=dict(raw.get("constraints", {})),
        required_passives=list(raw.get("required_passives", [])),
    )

