"""Deterministic pre-KiCad electrical rules checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..models.circuit_spec import CircuitSpec


@dataclass(frozen=True)
class ErcFinding:
    check_id: str
    severity: str
    category: str
    message: str
    module_name: str = ""
    net_name: str = ""
    suggestion: str = ""


@dataclass
class ErcReport:
    findings: list[ErcFinding] = field(default_factory=list)

    @property
    def errors(self) -> list[ErcFinding]:
        return [finding for finding in self.findings if finding.severity == "error"]

    @property
    def warnings(self) -> list[ErcFinding]:
        return [finding for finding in self.findings if finding.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.to_text(), encoding="utf-8")

    def to_text(self) -> str:
        lines = [
            "Electrical Rules Report",
            "=" * 60,
            f"Errors: {len(self.errors)}",
            f"Warnings: {len(self.warnings)}",
            "",
        ]
        if not self.findings:
            lines.append("No ERC findings.")
            return "\n".join(lines) + "\n"
        for finding in self.findings:
            lines.append(f"[{finding.severity.upper()}] {finding.check_id} ({finding.category})")
            if finding.module_name:
                lines.append(f"  Module: {finding.module_name}")
            if finding.net_name:
                lines.append(f"  Net: {finding.net_name}")
            lines.append(f"  {finding.message}")
            if finding.suggestion:
                lines.append(f"  Suggestion: {finding.suggestion}")
            lines.append("")
        return "\n".join(lines)


def run_preflight_erc(spec: CircuitSpec) -> ErcReport:
    findings: list[ErcFinding] = []
    rail_names = spec.rail_names
    net_names = spec.net_names
    protection_roles = set(spec.protection_roles)
    impedance_rules = set(spec.impedance_rules)

    for component in spec.components:
        if component.required and not component.rails and component.module_type not in {
            "switch",
            "debug",
        }:
            findings.append(ErcFinding(
                check_id="ERC-001",
                severity="error",
                category="power",
                module_name=component.name,
                message="Required module has no declared power rail.",
                suggestion="Add rails to the functional module definition.",
            ))
        for rail in component.rails:
            if rail not in rail_names:
                findings.append(ErcFinding(
                    check_id="ERC-001",
                    severity="error",
                    category="power",
                    module_name=component.name,
                    net_name=rail,
                    message="Required power rail is not declared as a voltage domain.",
                    suggestion="Declare this rail in hardware_platform.target_voltage_domains.",
                ))
        if component.module_type == "connector" and component.require_esd:
            if not _has_matching_protection(component.name, protection_roles):
                findings.append(ErcFinding(
                    check_id="ERC-003",
                    severity="warning",
                    category="protection",
                    module_name=component.name,
                    message=(
                        "Exposed connector requests ESD but no matching "
                        "protection rule was found."
                    ),
                    suggestion="Add a connector-specific protection rule or document a waiver.",
                ))
        if _is_usb_c(component) and "CC1" in component.target_nets:
            if "CC1" not in net_names:
                findings.append(ErcFinding(
                    check_id="ERC-004",
                    severity="error",
                    category="usb_c",
                    module_name=component.name,
                    net_name="CC1",
                    message="USB-C CC1 net is declared by module but absent from CircuitSpec nets.",
                    suggestion="Add CC1 to schematic or module target nets.",
                ))
            if not _param_mentions(component.params, ("cc", "pull", "role")):
                findings.append(ErcFinding(
                    check_id="ERC-004",
                    severity="warning",
                    category="usb_c",
                    module_name=component.name,
                    net_name="CC1",
                    message="USB-C role/CC pull resistor intent is not documented.",
                    suggestion="Add params for CC role and Rd/Rp resistor strategy.",
                ))
        if "i2c" in component.allowed_interfaces and not _param_mentions(
            component.params,
            ("pullup", "pull_up", "address", "telemetry"),
            extra_text=f"telemetry_bus={component.telemetry_bus}",
        ):
            findings.append(ErcFinding(
                check_id="ERC-005",
                severity="warning",
                category="i2c",
                module_name=component.name,
                message="I2C-capable module has no pull-up/address intent in params.",
                suggestion="Add pull-up ownership and I2C address where applicable.",
            ))
        if component.module_type == "switch" and any(
            net.upper() in {"NRST", "WKUP", "RESET"} for net in component.target_nets
        ):
            if "buttons" not in protection_roles:
                findings.append(ErcFinding(
                    check_id="ERC-006",
                    severity="warning",
                    category="button",
                    module_name=component.name,
                    message="Reset/wakeup button lacks button protection rule coverage.",
                    suggestion="Add RC debounce/ESD protection intent for user-facing buttons.",
                ))
        if component.module_type == "audio_dac":
            if not ({"mclk_clock", "i2s_mclk"} & impedance_rules):
                findings.append(ErcFinding(
                    check_id="ERC-009",
                    severity="warning",
                    category="audio_clock",
                    module_name=component.name,
                    net_name="I2S_MCK",
                    message="Audio DAC has no MCLK impedance/clock rule.",
                    suggestion="Add mclk_clock or i2s_mclk impedance control.",
                ))
        if _is_usb_c(component) and not {"usb_dp_dm", "usb"} & impedance_rules:
            findings.append(ErcFinding(
                check_id="ERC-010",
                severity="warning",
                category="usb",
                module_name=component.name,
                message="USB differential impedance rule is missing.",
                suggestion="Add usb_dp_dm impedance control.",
            ))

    return ErcReport(findings=findings)


def _has_matching_protection(module_name: str, protection_roles: set[str]) -> bool:
    normalized = module_name.lower()
    if "usb" in normalized:
        return any("usb" in role for role in protection_roles)
    if "headphone" in normalized:
        return any("headphone" in role for role in protection_roles)
    return normalized in protection_roles


def _is_usb_c(component) -> bool:
    return "usb" in component.name.lower() or "usb" in str(component.params.get("type", "")).lower()


def _param_mentions(
    params: dict,
    needles: tuple[str, ...],
    *,
    extra_text: str = "",
) -> bool:
    text = " ".join(
        [*(f"{key}={value}" for key, value in params.items()), extra_text]
    ).lower()
    return any(needle in text for needle in needles)
