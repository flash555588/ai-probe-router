"""Schematic-level design review: proactive checks beyond KiCad DRC/ERC.

Detects common hardware design issues such as missing decoupling caps,
strapping pin conflicts, incorrect ADC pin assignments, and missing
pull-up resistors.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..models.board import Board, Schematic
from .net_classifier import classify_net_detailed

if TYPE_CHECKING:
    from ..models.mcu_profile import McuProfile


@dataclass
class ReviewFinding:
    check_id: str
    severity: str  # "error" | "warning" | "info"
    category: str
    component_ref: str
    message: str
    suggestion: str
    net_name: str = ""
    pin_name: str = ""


@dataclass
class DesignReviewReport:
    findings: list[ReviewFinding] = field(default_factory=list)
    mcu_profile_name: str = ""

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warning")

    def summary(self) -> str:
        lines = [
            f"Design Review Report ({len(self.findings)} findings)",
            "=" * 60,
        ]
        if self.mcu_profile_name:
            lines.append(f"MCU Profile: {self.mcu_profile_name}")
            lines.append("")
        for f in self.findings:
            sev = f.severity.upper()
            lines.append(f"[{sev}] {f.check_id} ({f.category})")
            if f.component_ref:
                lines.append(f"  Component: {f.component_ref}")
            if f.net_name:
                lines.append(f"  Net: {f.net_name}")
            lines.append(f"  {f.message}")
            lines.append(f"  Suggestion: {f.suggestion}")
            lines.append("")
        lines.append(
            f"Summary: {self.error_count} errors, {self.warning_count} warnings, "
            f"{len(self.findings) - self.error_count - self.warning_count} info"
        )
        return "\n".join(lines)


def run_design_review(
    schematic: Schematic | None = None,
    board: Board | None = None,
    mcu_profile: McuProfile | None = None,
) -> DesignReviewReport:
    findings: list[ReviewFinding] = []

    if schematic:
        findings.extend(check_decoupling_caps(schematic, board))
        findings.extend(check_sd_card_pullups(schematic))
        findings.extend(check_battery_protection(schematic))
        findings.extend(check_power_path(schematic))
        if mcu_profile:
            findings.extend(check_strapping_pins(schematic, mcu_profile))
            findings.extend(check_adc_pin_mapping(schematic, mcu_profile))

    return DesignReviewReport(
        findings=findings,
        mcu_profile_name=mcu_profile.name if mcu_profile else "",
    )


def check_decoupling_caps(
    schematic: Schematic,
    board: Board | None = None,
) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    ics = [c for c in schematic.components if _is_ic(c)]
    caps = [c for c in schematic.components if _is_cap(c)]

    for ic in ics:
        ref = _comp_attr(ic, "ref", "")
        power_nets = _find_power_nets_for_component(ic, schematic)

        for pnet in power_nets:
            has_cap = any(
                _component_on_net(cap, pnet, schematic)
                for cap in caps
            )
            if not has_cap:
                findings.append(ReviewFinding(
                    check_id="DECAP-001",
                    severity="warning",
                    category="decoupling",
                    component_ref=ref,
                    net_name=pnet,
                    message=f"No decoupling capacitor found on power net '{pnet}' near {ref}",
                    suggestion=(
                        f"Add 100nF ceramic cap close to {ref} power pin, "
                        "plus 10uF bulk cap for ICs with high transient current"
                    ),
                ))

    return findings


def check_strapping_pins(
    schematic: Schematic,
    mcu_profile: McuProfile,
) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []

    net_names = schematic.net_names()
    for sp in mcu_profile.strapping_pins:
        gpio_num = re.search(r"\d+", sp.gpio)
        if not gpio_num:
            continue
        matching_nets = [
            n for n in net_names
            if re.search(rf"(GPIO|IO){gpio_num.group()}\b", n, re.I)
        ]
        for net_name in matching_nets:
            connected = _components_on_net(schematic, net_name)
            non_passive_loads = [
                c for c in connected
                if not _is_passive(c) and not _is_ic_with_ref(c, "U")
            ]
            if non_passive_loads:
                refs = ", ".join(_comp_attr(c, "ref", "?") for c in non_passive_loads)
                findings.append(ReviewFinding(
                    check_id="STRAP-001",
                    severity="warning",
                    category="strapping",
                    component_ref=refs,
                    net_name=net_name,
                    pin_name=sp.gpio,
                    message=(
                        f"Strapping pin {sp.gpio} ({sp.function}) has external loads: {refs}. "
                        f"Default state: {sp.default_state}. {sp.notes}"
                    ),
                    suggestion=(
                        "Ensure external loads do not override the required boot-time level. "
                        "Add a pull resistor matching the default state if needed."
                    ),
                ))

    return findings


def check_adc_pin_mapping(
    schematic: Schematic,
    mcu_profile: McuProfile,
) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    net_names = schematic.net_names()

    for net_name in net_names:
        _, sub_roles = classify_net_detailed(net_name)
        from ..models.net import NetSubRole
        if NetSubRole.ADC_INPUT not in sub_roles:
            continue

        gpio_match = re.search(r"(GPIO|IO)(\d+)", net_name, re.I)
        if not gpio_match:
            continue
        gpio_name = f"GPIO{gpio_match.group(2)}"

        if not mcu_profile.is_adc_capable(gpio_name):
            adc_gpios = sorted(
                {ch.gpio for ch in mcu_profile.adc_channels},
                key=lambda g: int(re.search(r"\d+", g).group()) if re.search(r"\d+", g) else 0,
            )
            adc_range = f"{adc_gpios[0]}-{adc_gpios[-1]}" if adc_gpios else "none"
            findings.append(ReviewFinding(
                check_id="ADC-001",
                severity="error",
                category="adc",
                component_ref="",
                net_name=net_name,
                pin_name=gpio_name,
                message=(
                    f"Net '{net_name}' appears to be an ADC input, but {gpio_name} "
                    f"does not support ADC on {mcu_profile.name}. "
                    f"ADC-capable GPIOs: {adc_range}."
                ),
                suggestion=(
                    f"Reassign the analog signal to an ADC-capable GPIO "
                    f"({adc_range} on {mcu_profile.name})."
                ),
            ))

    return findings


def check_sd_card_pullups(schematic: Schematic) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    net_names = schematic.net_names()
    sd_data_nets = [
        n for n in net_names
        if re.search(r"(SD_?DAT|SD_?D\d|SD_?CMD|SDIO_?D|SDIO_?CMD)", n, re.I)
    ]

    for net_name in sd_data_nets:
        resistors = [
            c for c in schematic.components
            if _is_resistor(c) and _component_on_net(c, net_name, schematic)
        ]
        has_pullup = False
        if resistors:
            power_nets = _all_power_nets(schematic)
            has_pullup = any(
                _component_on_net(r, pn, schematic)
                for r in resistors
                for pn in power_nets
            )
        if not has_pullup and not resistors:
            findings.append(ReviewFinding(
                check_id="SDPULL-001",
                severity="warning",
                category="pull_resistor",
                component_ref="",
                net_name=net_name,
                message=f"SD card line '{net_name}' has no pull-up resistor",
                suggestion="Add a 10k-47k pull-up resistor to 3.3V on SD data/CMD lines",
            ))

    return findings


def check_battery_protection(schematic: Schematic) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    net_names = schematic.net_names()
    battery_nets = [
        n for n in net_names
        if re.search(r"(VBAT|BAT|BATTERY|LI_?ION|CELL)", n, re.I)
    ]

    if not battery_nets:
        return findings

    protection_ics = [
        c for c in schematic.components
        if _is_battery_protection(c)
    ]

    if not protection_ics:
        findings.append(ReviewFinding(
            check_id="BATPROT-001",
            severity="warning",
            category="power",
            component_ref="",
            net_name=battery_nets[0],
            message="Li-ion battery detected but no protection IC found",
            suggestion=(
                "Add a battery protection IC (e.g., DW01 + MOSFET, or FS312) "
                "for over-discharge, over-charge, and short-circuit protection"
            ),
        ))

    return findings


def check_power_path(schematic: Schematic) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    net_names = schematic.net_names()

    has_usb = any(re.search(r"(VBUS|USB)", n, re.I) for n in net_names)
    has_battery = any(
        re.search(r"(VBAT|BAT|BATTERY|LI_?ION)", n, re.I) for n in net_names
    )

    if not (has_usb and has_battery):
        return findings

    power_path_components = [
        c for c in schematic.components
        if _is_power_path_controller(c)
    ]

    if not power_path_components:
        findings.append(ReviewFinding(
            check_id="PWRPATH-001",
            severity="info",
            category="power",
            component_ref="",
            message="USB and battery power coexist but no load-sharing circuit detected",
            suggestion=(
                "Consider adding a load-sharing circuit (ideal diode OR, "
                "or a power-path controller) to manage USB/battery switching"
            ),
        ))

    return findings


# --- Helper functions ---

def _comp_attr(component, attr: str, default=""):
    """Access component attribute whether it's a dict or a dataclass."""
    if isinstance(component, dict):
        return component.get(attr, default)
    return getattr(component, attr, default)


def _is_ic(component) -> bool:
    ref = _comp_attr(component, "ref", "")
    return ref.startswith("U") or ref.startswith("IC")


def _is_cap(component) -> bool:
    ref = _comp_attr(component, "ref", "")
    return ref.startswith("C") and not ref.startswith("CN")


def _is_resistor(component) -> bool:
    ref = _comp_attr(component, "ref", "")
    return ref.startswith("R")


def _is_passive(component) -> bool:
    ref = _comp_attr(component, "ref", "")
    return ref[:1] in {"R", "C", "L"} and not ref.startswith("CN")


def _is_ic_with_ref(component, prefix: str) -> bool:
    return _comp_attr(component, "ref", "").startswith(prefix)


def _is_battery_protection(component) -> bool:
    ref = _comp_attr(component, "ref", "")
    lib_id = _comp_attr(component, "lib_id", "")
    value = _comp_attr(component, "value", "")
    keywords = ("DW01", "FS312", "S8261", "BQ29", "XB5353", "HY2112")
    text = f"{ref} {lib_id} {value}".upper()
    return any(kw in text for kw in keywords)


def _is_power_path_controller(component) -> bool:
    lib_id = _comp_attr(component, "lib_id", "")
    value = _comp_attr(component, "value", "")
    text = f"{lib_id} {value}".upper()
    keywords = ("BQ24", "LTC4", "TPS2", "MAX1708", "IDEAL_DIODE", "LOAD_SHARE")
    return any(kw in text for kw in keywords)


def _find_power_nets_for_component(
    component,
    schematic: Schematic,
) -> list[str]:
    comp_x = _comp_attr(component, "x", 0.0)
    comp_y = _comp_attr(component, "y", 0.0)
    power_nets: list[str] = []
    seen: set[str] = set()
    for label in schematic.labels:
        name = label.get("name", "") if isinstance(label, dict) else getattr(label, "name", "")
        if not re.search(r"^(VCC|VDD|3V3|5V|1V8|VBUS|AVDD|DVDD|CPVDD)", name, re.I):
            continue
        if name in seen:
            continue
        lx = label.get("x", 0.0) if isinstance(label, dict) else getattr(label, "x", 0.0)
        ly = label.get("y", 0.0) if isinstance(label, dict) else getattr(label, "y", 0.0)
        dist = ((comp_x - lx) ** 2 + (comp_y - ly) ** 2) ** 0.5
        if dist < 50.0:
            seen.add(name)
            power_nets.append(name)
    return power_nets


def _component_on_net(
    component,
    net_name: str,
    schematic: Schematic,
) -> bool:
    comp_x = _comp_attr(component, "x", 0.0)
    comp_y = _comp_attr(component, "y", 0.0)
    for label in schematic.labels:
        lname = label.get("name", "") if isinstance(label, dict) else getattr(label, "name", "")
        if lname != net_name:
            continue
        lx = label.get("x", 0.0) if isinstance(label, dict) else getattr(label, "x", 0.0)
        ly = label.get("y", 0.0) if isinstance(label, dict) else getattr(label, "y", 0.0)
        dist = ((comp_x - lx) ** 2 + (comp_y - ly) ** 2) ** 0.5
        if dist < 30.0:
            return True
    return False


def _components_on_net(
    schematic: Schematic,
    net_name: str,
) -> list:
    result = []
    for comp in schematic.components:
        if _component_on_net(comp, net_name, schematic):
            result.append(comp)
    return result


def _all_power_nets(schematic: Schematic) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for label in schematic.labels:
        name = label.get("name", "") if isinstance(label, dict) else getattr(label, "name", "")
        if name in seen:
            continue
        if re.search(r"^(VCC|VDD|3V3|5V|1V8|VBUS|AVDD|DVDD)", name, re.I):
            seen.add(name)
            result.append(name)
    return result
