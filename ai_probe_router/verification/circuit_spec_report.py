"""Validate typed CircuitSpec before KiCad generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import get_close_matches
from pathlib import Path

from ..models.circuit_spec import CircuitSpec

KNOWN_INTERFACES = {
    "adc",
    "analog_diff",
    "gpio",
    "fpc_5p",
    "fpc_12p",
    "i2c",
    "i2s",
    "rgb_parallel",
    "sdio",
    "spi",
    "spi_quad",
    "swd",
    "usb_fs",
}


@dataclass(frozen=True)
class CircuitSpecIssue:
    severity: str
    code: str
    message: str
    module_name: str = ""
    suggestion: str = ""


@dataclass
class CircuitSpecReport:
    issues: list[CircuitSpecIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[CircuitSpecIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[CircuitSpecIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.to_text(), encoding="utf-8")

    def to_text(self) -> str:
        lines = [
            "CircuitSpec Validation Report",
            "=" * 60,
            f"Errors: {len(self.errors)}",
            f"Warnings: {len(self.warnings)}",
            "",
        ]
        if not self.issues:
            lines.append("No CircuitSpec issues found.")
            return "\n".join(lines) + "\n"
        for issue in self.issues:
            lines.append(f"[{issue.severity.upper()}] {issue.code}")
            if issue.module_name:
                lines.append(f"  Module: {issue.module_name}")
            lines.append(f"  {issue.message}")
            if issue.suggestion:
                lines.append(f"  Suggestion: {issue.suggestion}")
            lines.append("")
        return "\n".join(lines)


def validate_circuit_spec(spec: CircuitSpec) -> CircuitSpecReport:
    issues: list[CircuitSpecIssue] = []
    rail_names = spec.rail_names
    net_names = spec.net_names

    for component in spec.components:
        for interface in component.allowed_interfaces:
            if interface not in KNOWN_INTERFACES:
                suggestion = _interface_suggestion(interface)
                issues.append(CircuitSpecIssue(
                    severity="error",
                    code="SPEC-UNKNOWN-INTERFACE",
                    module_name=component.name,
                    message=f"Unknown interface '{interface}'.",
                    suggestion=(
                        f"Use '{suggestion}'."
                        if suggestion
                        else "Add the interface to KNOWN_INTERFACES."
                    ),
                ))
        param_interface = component.params.get("interface")
        if isinstance(param_interface, str) and param_interface not in KNOWN_INTERFACES:
            suggestion = _interface_suggestion(param_interface)
            issues.append(CircuitSpecIssue(
                severity="error",
                code="SPEC-UNKNOWN-PARAM-INTERFACE",
                module_name=component.name,
                message=f"Unknown params.interface '{param_interface}'.",
                suggestion=(
                    f"Use '{suggestion}'." if suggestion else "Correct or register this interface."
                ),
            ))
        for rail in component.rails:
            if rail not in rail_names:
                issues.append(CircuitSpecIssue(
                    severity="error",
                    code="SPEC-UNKNOWN-RAIL",
                    module_name=component.name,
                    message=(
                        f"Rail '{rail}' is not declared in "
                        "hardware_platform.target_voltage_domains."
                    ),
                    suggestion="Declare the voltage domain or update the module rail name.",
                ))
        for net in component.target_nets:
            if net not in net_names:
                issues.append(CircuitSpecIssue(
                    severity="warning",
                    code="SPEC-UNRESOLVED-TARGET-NET",
                    module_name=component.name,
                    message=f"Target net '{net}' is not present in schematic/probe/module net set.",
                    suggestion="Add the net to the schematic or generated CircuitSpec source.",
                ))
        if component.required and component.module_type == "connector" and component.require_esd:
            if not _has_matching_protection(component.name, set(spec.protection_roles)):
                issues.append(CircuitSpecIssue(
                    severity="warning",
                    code="SPEC-CONNECTOR-ESD-REVIEW",
                    module_name=component.name,
                    message=(
                        "Required connector requests ESD protection; "
                        "verify protection rule coverage."
                    ),
                    suggestion="Add a matching protection rule or waiver.",
                ))

    return CircuitSpecReport(issues=issues)


def _interface_suggestion(interface: str) -> str:
    matches = get_close_matches(interface, KNOWN_INTERFACES, n=1, cutoff=0.65)
    return matches[0] if matches else ""


def _has_matching_protection(module_name: str, protection_roles: set[str]) -> bool:
    normalized = module_name.lower()
    if "usb" in normalized:
        return any("usb" in role for role in protection_roles)
    if "headphone" in normalized:
        return any("headphone" in role for role in protection_roles)
    return normalized in protection_roles
