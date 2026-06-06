"""Protection components inserted between MCU nets and probe testpoints."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class ProtectionType(Enum):
    SERIES_RESISTOR = auto()
    FERRITE_BEAD = auto()


@dataclass
class ProtectionComponent:
    protection_type: ProtectionType
    value: str
    package: str = "0402"
    ref_prefix: str = "R"

    @property
    def footprint_name(self) -> str:
        w, h = _PACKAGE_SIZES[self.package]
        return f"Resistor_SMD:R_{self.package}_{w}x{h}Metric"

    @property
    def lib_symbol_name(self) -> str:
        if self.protection_type == ProtectionType.SERIES_RESISTOR:
            return "Device:R"
        return "Device:FerriteBead"


_PACKAGE_SIZES = {
    "0402": ("1005", "0500"),
    "0603": ("1608", "0800"),
    "0805": ("2012", "1200"),
}

ROLE_PROTECTION_DEFAULTS: dict[str, ProtectionComponent] = {
    "debug": ProtectionComponent(
        protection_type=ProtectionType.SERIES_RESISTOR,
        value="33",
        package="0402",
        ref_prefix="R",
    ),
    "reset": ProtectionComponent(
        protection_type=ProtectionType.SERIES_RESISTOR,
        value="100",
        package="0402",
        ref_prefix="R",
    ),
    "power": ProtectionComponent(
        protection_type=ProtectionType.FERRITE_BEAD,
        value="600R@100MHz",
        package="0603",
        ref_prefix="FB",
    ),
}


@dataclass
class ProtectionRules:
    rules: dict[str, ProtectionComponent] = field(default_factory=dict)
    enabled: bool = True

    def get_protection(self, role: str) -> ProtectionComponent | None:
        if not self.enabled:
            return None
        return self.rules.get(role)

    @staticmethod
    def with_defaults() -> ProtectionRules:
        return ProtectionRules(rules=dict(ROLE_PROTECTION_DEFAULTS))
