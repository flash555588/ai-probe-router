"""Top-level readiness verdict across generated reports."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..models.module_compatibility import ModuleCompatibilityResult
from ..models.module_library_preflight import ModuleLibraryPreflightResult
from ..routing.module_corridor import RoutingFeasibilityResult
from ..solvers.module_selector import ModuleSelectionResult
from ..solvers.pin_mapper import MappingResult
from ..synthesis.module_instantiator import ModuleInstantiationResult
from .design_process_report import DesignProcessReport
from .diff_pair_skew_report import DiffPairSkewReport
from .manufacturing_report import ManufacturingReport
from .report import CoverageReport


@dataclass
class ReadinessIssue:
    severity: str
    source: str
    message: str


@dataclass
class ReadinessReport:
    run_id: str = ""
    verdict: str = "PASS"
    issues: list[ReadinessIssue] = field(default_factory=list)

    @property
    def blockers(self) -> list[ReadinessIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ReadinessIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def infos(self) -> list[ReadinessIssue]:
        return [issue for issue in self.issues if issue.severity == "info"]

    def summary_text(self) -> str:
        lines = [
            "=" * 96,
            "  AI Probe Router - Readiness Summary",
            "=" * 96,
            "",
            f"  Verdict:   {self.verdict}",
            f"  Blockers:  {len(self.blockers)}",
            f"  Warnings:  {len(self.warnings)}",
            f"  Info:      {len(self.infos)}",
            "",
        ]
        if self.run_id:
            lines.insert(4, f"  Run ID:    {self.run_id}")
            lines.insert(5, "")
        if not self.issues:
            lines.append("  No blocking or review issues were reported.")
        else:
            lines.append("  Issues:")
            for issue in self.issues:
                lines.append(
                    f"    - [{issue.severity.upper()}] "
                    f"{issue.source}: {issue.message}"
                )
        lines.append("")
        lines.append("=" * 96)
        return "\n".join(lines)

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.summary_text(), encoding="utf-8")

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "verdict": self.verdict,
            "counts": {
                "blockers": len(self.blockers),
                "warnings": len(self.warnings),
                "infos": len(self.infos),
                "issues": len(self.issues),
            },
            "issues": [
                {
                    "severity": issue.severity,
                    "source": issue.source,
                    "message": issue.message,
                }
                for issue in self.issues
            ],
            "exit_code": readiness_exit_code(self.verdict),
        }

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def readiness_exit_code(verdict: str) -> int:
    if verdict == "PASS":
        return 0
    if verdict == "PASS_WITH_REVIEW":
        return 2
    if verdict == "BLOCKED":
        return 3
    return 1


def generate_readiness_report(
    coverage: CoverageReport,
    *,
    run_id: str = "",
    module_library_preflight: ModuleLibraryPreflightResult | None = None,
    module_selection: ModuleSelectionResult | None = None,
    module_graph_result=None,
    module_compatibility_result: ModuleCompatibilityResult | None = None,
    module_placement_result=None,
    module_instantiation_result: ModuleInstantiationResult | None = None,
    routing_feasibility: RoutingFeasibilityResult | None = None,
    pin_mapping_result: MappingResult | None = None,
    manufacturing_report: ManufacturingReport | None = None,
    diff_pair_report: DiffPairSkewReport | None = None,
    process_report: DesignProcessReport | None = None,
) -> ReadinessReport:
    report = ReadinessReport(run_id=run_id or coverage.run_id)

    _add_module_library_preflight(report, module_library_preflight)
    _add_module_selection(report, module_selection)
    _add_module_graph(report, module_graph_result)
    _add_module_compatibility(report, module_compatibility_result)
    _add_module_placement(report, module_placement_result)
    _add_module_instantiation(report, module_instantiation_result)
    _add_routing_feasibility(report, routing_feasibility)
    _add_pin_mapping(report, pin_mapping_result)
    _add_coverage(report, coverage)
    _add_manufacturing(report, manufacturing_report)
    _add_diff_pair_skew(report, diff_pair_report)
    _add_process_control(report, process_report)

    if report.blockers:
        report.verdict = "BLOCKED"
    elif report.warnings:
        report.verdict = "PASS_WITH_REVIEW"
    else:
        report.verdict = "PASS"
    return report


def _add_issue(
    report: ReadinessReport,
    severity: str,
    source: str,
    message: str,
) -> None:
    report.issues.append(ReadinessIssue(severity, source, message))


def _add_many(
    report: ReadinessReport,
    severity: str,
    source: str,
    messages: list[str],
) -> None:
    for message in messages:
        _add_issue(report, severity, source, message)


def _add_module_library_preflight(
    report: ReadinessReport,
    result: ModuleLibraryPreflightResult | None,
) -> None:
    if result is None:
        return
    _add_many(report, "error", "module_library_preflight", result.errors)
    _add_many(report, "warning", "module_library_preflight", result.warnings)


def _add_module_selection(
    report: ReadinessReport,
    result: ModuleSelectionResult | None,
) -> None:
    if result is None:
        return
    _add_many(report, "error", "module_selection", result.errors)
    _add_many(report, "warning", "module_selection", result.warnings)


def _add_module_graph(report: ReadinessReport, result) -> None:
    if result is None:
        return
    _add_many(report, "error", "module_graph", result.errors)
    _add_many(report, "warning", "module_graph", result.warnings)
    _add_many(report, "info", "module_graph", result.ignored_hints)


def _add_module_compatibility(
    report: ReadinessReport,
    result: ModuleCompatibilityResult | None,
) -> None:
    if result is None:
        return
    _add_many(report, "error", "module_compatibility", result.errors)
    _add_many(report, "warning", "module_compatibility", result.warnings)


def _add_module_placement(report: ReadinessReport, result) -> None:
    if result is None:
        return
    if result.skipped:
        _add_issue(
            report,
            "warning",
            "module_placement",
            f"skipped ({result.skip_reason})",
        )
    _add_many(report, "error", "module_placement", result.errors)
    _add_many(report, "warning", "module_placement", result.warnings)


def _add_module_instantiation(
    report: ReadinessReport,
    result: ModuleInstantiationResult | None,
) -> None:
    if result is None:
        return
    if result.skipped:
        _add_issue(
            report,
            "warning",
            "module_instantiation",
            f"skipped ({result.skip_reason})",
        )
    _add_many(report, "warning", "module_instantiation", result.warnings)


def _add_routing_feasibility(
    report: ReadinessReport,
    result: RoutingFeasibilityResult | None,
) -> None:
    if result is None:
        return
    if result.skipped:
        _add_issue(
            report,
            "warning",
            "routing_feasibility",
            f"skipped ({result.skip_reason})",
        )
        return
    for corridor in result.corridors:
        if not corridor.ok:
            _add_issue(
                report,
                "error",
                "routing_feasibility",
                f"{corridor.source_id}->{corridor.target_id}: {corridor.message}",
            )
    _add_many(report, "warning", "routing_feasibility", result.warnings)


def _add_pin_mapping(
    report: ReadinessReport,
    result: MappingResult | None,
) -> None:
    if result is None:
        return
    _add_many(report, "error", "pin_mapping", result.errors)
    for req in result.unmapped:
        severity = "error" if req.required else "warning"
        _add_issue(
            report,
            severity,
            "pin_mapping",
            f"unmapped net {req.net_name} (role={req.role})",
        )


def _add_coverage(report: ReadinessReport, coverage: CoverageReport) -> None:
    if coverage.total_nets_requested and not coverage.entries and coverage.missing:
        _add_issue(
            report,
            "error",
            "testpoint_coverage",
            f"{coverage.missing} requested net(s) were not evaluated",
        )
    for entry in coverage.entries:
        if entry.has_testpoint:
            continue
        severity = "error" if entry.required else "warning"
        _add_issue(
            report,
            severity,
            "testpoint_coverage",
            f"{entry.net_name} has no generated testpoint",
        )

    if coverage.constraint_ok is False:
        _add_many(report, "error", "constraints", coverage.constraint_messages)
    if coverage.erc_ok is False:
        _add_issue(
            report,
            "error",
            "erc",
            f"{coverage.erc_violations} ERC violation(s)",
        )
    if coverage.drc_ok is False:
        _add_issue(
            report,
            "error",
            "drc",
            f"{coverage.drc_violations} DRC violation(s)",
        )
    if coverage.routing_ok is False:
        _add_many(report, "error", "probe_routing", coverage.routing_messages)
        if not coverage.routing_messages:
            _add_issue(
                report,
                "error",
                "probe_routing",
                f"{coverage.unrouted_connections} unrouted connection(s)",
            )
    for entry in coverage.entries:
        if entry.review_required:
            _add_issue(
                report,
                "warning",
                "human_review",
                f"{entry.net_name} requires review",
            )


def _add_manufacturing(
    report: ReadinessReport,
    result: ManufacturingReport | None,
) -> None:
    if result is None:
        return
    if not result.board_outline_ok:
        _add_issue(
            report,
            "warning",
            "manufacturing",
            "board outline missing or board was not parsed",
        )
    if result.testpoint_coverage_pct < 100.0:
        _add_issue(
            report,
            "warning",
            "manufacturing",
            f"testpoint coverage is {result.testpoint_coverage_pct:.1f}%",
        )
    if result.review_gate_count:
        _add_issue(
            report,
            "warning",
            "manufacturing",
            f"{result.review_gate_count} review gate(s)",
        )


def _add_diff_pair_skew(
    report: ReadinessReport,
    result: DiffPairSkewReport | None,
) -> None:
    if result is None:
        return
    for pair in result.pairs:
        if pair.ok:
            continue
        _add_issue(
            report,
            "error",
            "diff_pair_skew",
            f"{pair.net_a}/{pair.net_b} skew {pair.skew_mm:+.2f}mm",
        )


def _add_process_control(
    report: ReadinessReport,
    result: DesignProcessReport | None,
) -> None:
    if result is None:
        return
    for issue in result.open_errors:
        _add_issue(
            report,
            "error",
            f"process:{issue.source}",
            f"{issue.issue_id}: {issue.message}",
        )
    for issue in result.open_warnings:
        _add_issue(
            report,
            "warning",
            f"process:{issue.source}",
            f"{issue.issue_id}: {issue.message}",
        )
    for issue in result.waived_issues:
        _add_issue(
            report,
            "info",
            f"process:{issue.source}",
            f"waived by {issue.waiver_id}: {issue.issue_id}",
        )
