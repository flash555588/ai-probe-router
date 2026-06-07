"""Protection components inserted between MCU nets and probe testpoints."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class ProtectionType(Enum):
    SERIES_RESISTOR = auto()
    FERRITE_BEAD = auto()
    ESD_ARRAY = auto()
    RC_FILTER = auto()
    LEVEL_SHIFTER = auto()
    CURRENT_LIMITER = auto()
    JUMPER = auto()
    RESISTOR_ARRAY = auto()
    TVS_DIODE = auto()
    COMMON_MODE_CHOKE = auto()
    IDEAL_DIODE = auto()
    EFUSE = auto()


@dataclass
class ProtectionComponent:
    protection_type: ProtectionType
    value: str
    package: str = "0402"
    ref_prefix: str = "R"

    @property
    def footprint_name(self) -> str:
        if self.protection_type == ProtectionType.JUMPER:
            return "Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm"
        if self.protection_type in {
            ProtectionType.ESD_ARRAY,
            ProtectionType.LEVEL_SHIFTER,
            ProtectionType.CURRENT_LIMITER,
            ProtectionType.EFUSE,
        }:
            return "Package_TO_SOT_SMD:SOT-23-6"
        if self.protection_type in {
            ProtectionType.TVS_DIODE,
            ProtectionType.IDEAL_DIODE,
        }:
            return "Diode_SMD:D_SOD-323"
        w, h = _PACKAGE_SIZES[self.package]
        return f"Resistor_SMD:R_{self.package}_{w}x{h}Metric"

    @property
    def lib_symbol_name(self) -> str:
        if self.protection_type in {
            ProtectionType.SERIES_RESISTOR,
            ProtectionType.RC_FILTER,
            ProtectionType.RESISTOR_ARRAY,
        }:
            return "Device:R"
        if self.protection_type == ProtectionType.FERRITE_BEAD:
            return "Device:FerriteBead"
        if self.protection_type == ProtectionType.JUMPER:
            return "Jumper:SolderJumper_2_Open"
        if self.protection_type in {
            ProtectionType.ESD_ARRAY,
            ProtectionType.TVS_DIODE,
            ProtectionType.IDEAL_DIODE,
        }:
            return "Device:D_TVS"
        if self.protection_type in {
            ProtectionType.CURRENT_LIMITER,
            ProtectionType.EFUSE,
        }:
            return "Device:Fuse"
        return "Device:R"


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


_PROTECTION_TYPE_ALIASES: dict[str, ProtectionType] = {
    "series_resistor": ProtectionType.SERIES_RESISTOR,
    "resistor": ProtectionType.SERIES_RESISTOR,
    "ferrite_bead": ProtectionType.FERRITE_BEAD,
    "ferrite": ProtectionType.FERRITE_BEAD,
    "esd": ProtectionType.ESD_ARRAY,
    "esd_array": ProtectionType.ESD_ARRAY,
    "rc_filter": ProtectionType.RC_FILTER,
    "level_shifter": ProtectionType.LEVEL_SHIFTER,
    "current_limiter": ProtectionType.CURRENT_LIMITER,
    "jumper": ProtectionType.JUMPER,
    "resistor_array": ProtectionType.RESISTOR_ARRAY,
    "tvs": ProtectionType.TVS_DIODE,
    "tvs_diode": ProtectionType.TVS_DIODE,
    "common_mode_choke": ProtectionType.COMMON_MODE_CHOKE,
    "ideal_diode": ProtectionType.IDEAL_DIODE,
    "efuse": ProtectionType.EFUSE,
}


def protection_type_from_string(value: str) -> ProtectionType:
    key = str(value).strip().lower().replace("-", "_")
    return _PROTECTION_TYPE_ALIASES.get(key, ProtectionType.SERIES_RESISTOR)
