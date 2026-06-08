"""GUI-friendly merged report model for plugin shell.

Joins footprint preview, resource allocation, and readiness data into
per-module summaries suitable for display in a detail panel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..report_utils import UnifiedReports


@dataclass
class ModuleReportSummary:
    module_name: str
    reference: str | None = None
    footprint: str | None = None
    footprint_issues: list[dict[str, Any]] = field(default_factory=list)
    resource_assignments: list[dict[str, Any]] = field(default_factory=list)
    resource_issues: list[dict[str, Any]] = field(default_factory=list)
    route_import_issues: list[dict[str, Any]] = field(default_factory=list)
    readiness_codes: list[str] = field(default_factory=list)

    @property
    def severity(self) -> str:
        all_issues = (
            self.footprint_issues
            + self.resource_issues
            + self.route_import_issues
        )
        severities = {issue.get("severity", "") for issue in all_issues}
        if "error" in severities:
            return "error"
        if "warning" in severities:
            return "warning"
        return "info"


class PluginReportModel:
    """Merged view model over all loaded reports."""

    def __init__(self, reports: UnifiedReports) -> None:
        self.reports = reports

    def module_summary(
        self,
        module_name: str,
        reference: str | None = None,
    ) -> ModuleReportSummary:
        return ModuleReportSummary(
            module_name=module_name,
            reference=reference,
            footprint=self._find_footprint(module_name, reference),
            footprint_issues=self._footprint_issues(module_name, reference),
            resource_assignments=self._resource_assignments(module_name),
            resource_issues=self._resource_issues(module_name),
            route_import_issues=self._route_import_issues(),
            readiness_codes=self._readiness_codes(module_name),
        )

    def _find_footprint(
        self, module_name: str, reference: str | None
    ) -> str | None:
        data = self.reports.footprint_preview
        if data is None:
            return None
        for fp in data.footprints:
            if fp.module_name == module_name and (
                reference is None or fp.reference == reference
            ):
                return fp.footprint
        return None

    def _footprint_issues(
        self, module_name: str, reference: str | None
    ) -> list[dict[str, Any]]:
        data = self.reports.footprint_preview
        if data is None:
            return []
        return [
            {
                "severity": i.severity,
                "code": i.code,
                "message": i.message,
                "reference": i.reference,
            }
            for i in data.issues
            if i.module_name == module_name
            and (reference is None or i.reference == reference)
        ]

    def _resource_assignments(self, module_name: str) -> list[dict[str, Any]]:
        data = self.reports.resource_allocation
        if data is None:
            return []
        assignments: list[dict[str, Any]] = []
        for bus in data.buses:
            if bus.module == module_name:
                assignments.append(
                    {
                        "type": "bus",
                        "bus_type": bus.bus_type,
                        "bus_id": bus.bus_id,
                        "address": bus.address,
                    }
                )
        for domain in data.power:
            assignments.append(
                {
                    "type": "power",
                    "domain": domain.domain,
                    "voltage": domain.voltage,
                    "requested_ma": domain.requested_ma,
                    "headroom": domain.headroom_percent,
                }
            )
        return assignments

    def _resource_issues(self, module_name: str) -> list[dict[str, Any]]:
        data = self.reports.resource_allocation
        if data is None:
            return []
        return [
            {"message": err}
            for err in data.errors
            if module_name in err
        ] + [
            {"message": warn, "severity": "warning"}
            for warn in data.warnings
            if module_name in warn
        ]

    def _route_import_issues(self) -> list[dict[str, Any]]:
        data = self.reports.readiness
        if data is None:
            return []
        return [
            {"severity": i.severity, "source": i.source, "message": i.message}
            for i in data.blockers + data.warnings
            if "route" in i.source.lower() or "import" in i.source.lower()
        ]

    def _readiness_codes(self, module_name: str) -> list[str]:
        data = self.reports.readiness
        if data is None:
            return []
        codes = []
        for issue in data.blockers + data.warnings:
            if issue.source in (None, "", module_name, "footprint_preview"):
                codes.append(issue.message)
        return codes
