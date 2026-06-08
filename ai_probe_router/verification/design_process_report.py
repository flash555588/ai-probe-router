"""Design-process coverage, waiver, and gap report."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..config import ProjectConfig
from ..models.board import Board
from ..models.module_compatibility import ModuleCompatibilityResult
from ..models.module_graph import ModuleGraphResult
from ..models.net import NetRole
from ..models.process_control import ProcessWaiver
from ..routing.freerouting_bridge import RoutingResult
from ..routing.module_corridor import RoutingFeasibilityResult
from .diff_pair_skew_report import DiffPairSkewReport
from .manufacturing_report import ManufacturingReport
from .report import CoverageReport


@dataclass
class ProcessIssue:
    severity: str
    source: str
    issue_id: str
    message: str
    recommendation: str = ""
    status: str = "open"
    waiver_id: str = ""


@dataclass
class DesignProcessReport:
    run_id: str = ""
    prior_run_id: str = ""
    issues: list[ProcessIssue] = field(default_factory=list)

    @property
    def open_errors(self) -> list[ProcessIssue]:
        return [
            issue for issue in self.issues
            if issue.status == "open" and issue.severity == "error"
        ]

    @property
    def open_warnings(self) -> list[ProcessIssue]:
        return [
            issue for issue in self.issues
            if issue.status == "open" and issue.severity == "warning"
        ]

    @property
    def waived_issues(self) -> list[ProcessIssue]:
        return [issue for issue in self.issues if issue.status == "waived"]

    def summary_text(self) -> str:
        lines = [
            "=" * 96,
            "  AI Probe Router - Design Process Report",
            "=" * 96,
            "",
        ]
        if self.run_id:
            lines.append(f"  Run ID:        {self.run_id}")
        if self.prior_run_id:
            lines.append(f"  Prior Run ID:  {self.prior_run_id}")
        lines.extend([
            f"  Open errors:   {len(self.open_errors)}",
            f"  Open warnings: {len(self.open_warnings)}",
            f"  Waived issues: {len(self.waived_issues)}",
            "",
        ])

        for source in _PROCESS_SOURCES:
            source_issues = [issue for issue in self.issues if issue.source == source]
            lines.append(f"  {source}:")
            if not source_issues:
                lines.append("    - [INFO] covered: no process gaps reported")
                continue
            for issue in source_issues:
                status = f" {issue.status.upper()}"
                if issue.waiver_id:
                    status += f" by {issue.waiver_id}"
                lines.append(
                    f"    - [{issue.severity.upper()}]{status} "
                    f"{issue.issue_id}: {issue.message}"
                )
                if issue.recommendation:
                    lines.append(f"      next: {issue.recommendation}")
        lines.append("")
        lines.append("=" * 96)
        return "\n".join(lines)

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.summary_text(), encoding="utf-8")


_PROCESS_SOURCES = [
    "electrical_signoff",
    "power_integrity",
    "manufacturing_dfm",
    "fixture_realism",
    "library_governance",
    "human_override",
    "incremental_diff",
    "scalability",
    "autorouter_feedback",
    "reproducibility",
]


def generate_design_process_report(
    cfg: ProjectConfig,
    *,
    run_id: str = "",
    board: Board | None = None,
    coverage: CoverageReport | None = None,
    module_graph_result: ModuleGraphResult | None = None,
    module_compatibility_result: ModuleCompatibilityResult | None = None,
    routing_feasibility: RoutingFeasibilityResult | None = None,
    manufacturing_report: ManufacturingReport | None = None,
    diff_pair_report: DiffPairSkewReport | None = None,
    autoroute_result: RoutingResult | None = None,
    prior_manifest: dict | None = None,
    generated_artifacts: set[str] | None = None,
) -> DesignProcessReport:
    report = DesignProcessReport(
        run_id=run_id or (coverage.run_id if coverage is not None else ""),
        prior_run_id=str((prior_manifest or {}).get("run_id", "")),
    )
    artifacts = generated_artifacts or set()

    _add_electrical(report, cfg, coverage, module_graph_result, diff_pair_report)
    _add_power(report, cfg, coverage, module_graph_result)
    _add_manufacturing(report, cfg, board, manufacturing_report, artifacts)
    _add_fixture(report, cfg, coverage, board)
    _add_library(report, module_graph_result, module_compatibility_result)
    _add_human_override(report, cfg.process_controls.waivers)
    _add_incremental_diff(report, prior_manifest)
    _add_scalability(report, cfg, module_graph_result)
    _add_autorouter(report, cfg, board, routing_feasibility, autoroute_result)
    _add_reproducibility(report, run_id, artifacts)
    _apply_waivers(
        report,
        cfg.process_controls.waivers,
        strict=cfg.process_controls.strict_signoff,
    )
    return report


def _add(
    report: DesignProcessReport,
    severity: str,
    source: str,
    issue_id: str,
    message: str,
    recommendation: str = "",
) -> None:
    report.issues.append(ProcessIssue(severity, source, issue_id, message, recommendation))


def _add_electrical(
    report: DesignProcessReport,
    cfg: ProjectConfig,
    coverage: CoverageReport | None,
    module_graph_result: ModuleGraphResult | None,
    diff_pair_report: DiffPairSkewReport | None,
) -> None:
    entries = coverage.entries if coverage is not None else []
    review_nets = [
        entry.net_name for entry in entries
        if entry.review_required
        or entry.role in {NetRole.ANALOG, NetRole.HIGH_SPEED, NetRole.CLOCK}
    ]
    if review_nets:
        _add(
            report,
            "warning",
            "electrical_signoff",
            "electrical_review_required",
            f"{len(review_nets)} sensitive net(s) need electrical review",
            "Capture impedance, return path, crosstalk, and analog/RF isolation decisions.",
        )
    diff_pair_without_rules = (
        diff_pair_report is not None
        and diff_pair_report.pairs
        and not cfg.impedance_control.has_rules()
    )
    if diff_pair_without_rules:
        _add(
            report,
            "warning",
            "electrical_signoff",
            "diff_pair_without_impedance_rules",
            "Differential-pair checks ran without configured impedance targets",
            "Add impedance_control rules for each high-speed differential interface.",
        )
    if module_graph_result is not None:
        for group in module_graph_result.graph.bus_groups:
            if group.bus_type == "i2c" and group.pullup_required and not group.pullup_covered:
                _add(
                    report,
                    "warning",
                    "electrical_signoff",
                    "i2c_pullup_missing",
                    f"I2C bus for modules {', '.join(group.modules)} lacks known pull-up coverage",
                    "Add pull-up components or library metadata proving coverage and sizing.",
                )
            for conflict in group.conflicts:
                _add(
                    report,
                    "warning",
                    "electrical_signoff",
                    "bus_conflict_requires_review",
                    conflict,
                    "Resolve address/chip-select contention before layout signoff.",
                )
    if not entries and module_graph_result is None:
        _add(
            report,
            "info",
            "electrical_signoff",
            "electrical_scope_empty",
            "No probe nets or module graph were available for electrical process checks",
        )


def _add_power(
    report: DesignProcessReport,
    cfg: ProjectConfig,
    coverage: CoverageReport | None,
    module_graph_result: ModuleGraphResult | None,
) -> None:
    if module_graph_result is not None:
        for domain in module_graph_result.graph.power_domains:
            if not domain.max_current_ma:
                _add(
                    report,
                    "warning",
                    "power_integrity",
                    "power_budget_unspecified",
                    f"{domain.domain_name} has estimated load but no current budget",
                    "Declare target_voltage_domains.max_current_ma for each rail.",
                )
            for warning in domain.warnings:
                _add(
                    report,
                    "warning",
                    "power_integrity",
                    "power_domain_warning",
                    warning,
                    "Review current limits, regulator margin, and copper adequacy.",
                )
    high_current = [
        req.net_name for req in cfg.nets_to_expose
        if req.current_ma and req.current_ma > 500
    ]
    if high_current and not cfg.thermal_analysis.enabled:
        _add(
            report,
            "warning",
            "power_integrity",
            "high_current_without_thermal_export",
            f"{len(high_current)} high-current net(s) lack thermal analysis export",
            "Enable thermal_analysis or attach an external PI/thermal signoff artifact.",
        )
    if coverage is not None and not module_graph_result and not high_current:
        _add(report, "info", "power_integrity", "power_scope_basic", "No advanced PI risks found")


def _add_manufacturing(
    report: DesignProcessReport,
    cfg: ProjectConfig,
    board: Board | None,
    manufacturing_report: ManufacturingReport | None,
    artifacts: set[str],
) -> None:
    if board is None:
        _add(
            report,
            "warning",
            "manufacturing_dfm",
            "board_missing_for_dfm",
            "No parsed board was available for DFM process checks",
            "Provide a PCB file to check board outline, tooling, and manufacturing exports.",
        )
        return
    if manufacturing_report is not None and not manufacturing_report.board_outline_ok:
        _add(
            report,
            "warning",
            "manufacturing_dfm",
            "board_outline_missing",
            "Board outline is missing or could not be parsed",
            "Fix Edge.Cuts before manufacturing release.",
        )
    if cfg.process_controls.require_manufacturing_exports:
        required = {
            "manufacturing/placement.csv",
        }
        missing = sorted(required - artifacts)
        if missing:
            _add(
                report,
                "warning",
                "manufacturing_dfm",
                "manufacturing_exports_missing",
                f"Required manufacturing artifact(s) missing: {', '.join(missing)}",
                "Generate Gerber, drill, and placement outputs before release.",
            )
    else:
        _add(
            report,
            "info",
            "manufacturing_dfm",
            "dfm_exports_advisory",
            "Manufacturing export completeness is advisory; strict export gate is disabled",
        )


def _add_fixture(
    report: DesignProcessReport,
    cfg: ProjectConfig,
    coverage: CoverageReport | None,
    board: Board | None,
) -> None:
    if coverage is not None and coverage.coverage_pct < 100.0:
        _add(
            report,
            "warning",
            "fixture_realism",
            "fixture_coverage_incomplete",
            f"Testpoint coverage is {coverage.coverage_pct:.1f}%",
            "Review inaccessible nets or lower the required coverage explicitly.",
        )
    if board is not None and not cfg.probe.require_fiducials:
        _add(
            report,
            "warning",
            "fixture_realism",
            "fixture_fiducials_not_required",
            "Probe fixture alignment fiducials are not required by config",
            "Require fiducials for repeatable pogo/bed-of-nails alignment.",
        )
    if board is not None and not cfg.probe.require_tooling_holes:
        _add(
            report,
            "warning",
            "fixture_realism",
            "fixture_tooling_not_required",
            "Fixture tooling holes are not required by config",
            "Require tooling holes or document the alternate mechanical datum.",
        )


def _add_library(
    report: DesignProcessReport,
    module_graph_result: ModuleGraphResult | None,
    module_compatibility_result: ModuleCompatibilityResult | None,
) -> None:
    if module_graph_result is None:
        _add(report, "info", "library_governance", "module_library_not_used", "No modules used")
        return
    if module_compatibility_result is not None:
        for warning in module_compatibility_result.warnings:
            _add(
                report,
                "warning",
                "library_governance",
                "library_metadata_review",
                warning,
                "Complete version, alternate, package, and lifecycle metadata.",
            )
        for error in module_compatibility_result.errors:
            _add(
                report,
                "warning",
                "library_governance",
                "library_compatibility_error",
                error,
                "Resolve library/version mismatch before release.",
            )


def _add_human_override(report: DesignProcessReport, waivers: list[ProcessWaiver]) -> None:
    if not waivers:
        _add(
            report,
            "info",
            "human_override",
            "waiver_registry_empty",
            "No process waivers were configured for this run",
        )
        return
    for waiver in waivers:
        if not waiver.complete:
            _add(
                report,
                "warning",
                "human_override",
                "waiver_incomplete",
                f"Waiver {waiver.waiver_id or '<missing-id>'} is missing required metadata",
                "Set waiver_id, issue_id, owner, and reason.",
            )


def _add_incremental_diff(
    report: DesignProcessReport,
    prior_manifest: dict | None,
) -> None:
    if not prior_manifest:
        _add(
            report,
            "info",
            "incremental_diff",
            "no_prior_manifest",
            "No previous decision manifest found; this run becomes the diff baseline",
        )
        return
    prior = str(prior_manifest.get("run_id", "unknown"))
    _add(
        report,
        "info",
        "incremental_diff",
        "prior_manifest_found",
        f"Previous decision manifest found for {prior}",
    )


def _add_scalability(
    report: DesignProcessReport,
    cfg: ProjectConfig,
    module_graph_result: ModuleGraphResult | None,
) -> None:
    module_count = (
        len(module_graph_result.graph.instances)
        if module_graph_result is not None else len(cfg.functional_modules)
    )
    net_count = len(cfg.nets_to_expose)
    if module_count > cfg.process_controls.scalability_module_warning_threshold:
        _add(
            report,
            "warning",
            "scalability",
            "module_count_scalability_threshold",
            f"{module_count} module(s) exceed configured scalability threshold",
            "Use hierarchical planning or raise the reviewed threshold.",
        )
    if net_count > cfg.process_controls.scalability_net_warning_threshold:
        _add(
            report,
            "warning",
            "scalability",
            "net_count_scalability_threshold",
            f"{net_count} requested net(s) exceed configured scalability threshold",
            "Enable staged runs or split the design into reviewed module groups.",
        )
    if module_count <= cfg.process_controls.scalability_module_warning_threshold and (
        net_count <= cfg.process_controls.scalability_net_warning_threshold
    ):
        _add(report, "info", "scalability", "scalability_budget_ok", "Size thresholds are OK")


def _add_autorouter(
    report: DesignProcessReport,
    cfg: ProjectConfig,
    board: Board | None,
    routing_feasibility: RoutingFeasibilityResult | None,
    autoroute_result: RoutingResult | None,
) -> None:
    if board is None:
        _add(report, "info", "autorouter_feedback", "autorouter_no_board", "No board to route")
        return
    if routing_feasibility is not None and routing_feasibility.skipped:
        _add(
            report,
            "warning",
            "autorouter_feedback",
            "routing_feasibility_skipped",
            f"Module corridor analysis skipped: {routing_feasibility.skip_reason}",
            "Provide a parseable board outline before relying on routing feasibility.",
        )
    if autoroute_result is None:
        severity = "error" if cfg.process_controls.require_autorouter_feedback else "warning"
        _add(
            report,
            severity,
            "autorouter_feedback",
            "autorouter_not_run",
            "No external autorouter result was captured",
            "Run FreeRouting or disable the autorouter feedback gate for advisory runs.",
        )
    elif not autoroute_result.ok:
        severity = "error" if cfg.process_controls.require_autorouter_feedback else "warning"
        _add(
            report,
            severity,
            "autorouter_feedback",
            "autorouter_feedback_missing",
            autoroute_result.error or "External autorouter did not produce routed feedback",
            "Install/configure FreeRouting or review DSN/SES handoff manually.",
        )
    else:
        _add(
            report,
            "info",
            "autorouter_feedback",
            "autorouter_feedback_ok",
            f"External autorouter completed in {autoroute_result.duration_sec:.1f}s",
        )


def _add_reproducibility(
    report: DesignProcessReport,
    run_id: str,
    artifacts: set[str],
) -> None:
    if not run_id:
        _add(
            report,
            "warning",
            "reproducibility",
            "run_id_missing",
            "Run ID is missing",
            "Generate deterministic run IDs before publishing outputs.",
        )
    if "decision_manifest.json" not in artifacts:
        _add(
            report,
            "info",
            "reproducibility",
            "decision_manifest_pending",
            "decision_manifest.json will be written after readiness is generated",
        )


def _apply_waivers(
    report: DesignProcessReport,
    waivers: list[ProcessWaiver],
    *,
    strict: bool = False,
) -> None:
    complete_waivers = [waiver for waiver in waivers if waiver.complete]
    for issue in report.issues:
        if issue.severity == "info":
            continue
        waiver = _matching_waiver(issue, complete_waivers)
        if waiver is None:
            if strict:
                issue.severity = "error"
            continue
        issue.status = "waived"
        issue.waiver_id = waiver.waiver_id


def _matching_waiver(
    issue: ProcessIssue,
    waivers: list[ProcessWaiver],
) -> ProcessWaiver | None:
    for waiver in waivers:
        if waiver.issue_id != issue.issue_id:
            continue
        if waiver.source and waiver.source != issue.source:
            continue
        return waiver
    return None
