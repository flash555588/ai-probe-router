"""Quality gate: metric-based pass/fail for generated artifacts.

Replaces "test -f" file-existence checks with threshold assertions on
actual engineering metrics: coverage, routing completion, ERC/DRC, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .report import CoverageReport


@dataclass
class QualityThresholds:
    """Configurable thresholds for the quality gate."""

    min_coverage_pct: float = 100.0
    max_unrouted_connections: int = 0
    max_total_route_bends: int | None = None
    require_erc_pass: bool = True
    require_drc_pass: bool = True
    require_routing_pass: bool = True
    require_constraint_pass: bool = False
    max_erc_violations: int = 0
    max_drc_violations: int = 0


@dataclass
class QualityGateResult:
    passed: bool = False
    failures: list[str] = field(default_factory=list)
    metrics: dict[str, object] = field(default_factory=dict)


def check_quality_gate(
    report: CoverageReport,
    thresholds: QualityThresholds | None = None,
) -> QualityGateResult:
    """Check a CoverageReport against thresholds.

    Returns a QualityGateResult with *passed* False if any threshold is
    violated, together with human-readable failure reasons.
    """
    if thresholds is None:
        thresholds = QualityThresholds()

    failures: list[str] = []
    metrics: dict[str, object] = {
        "coverage_pct": report.coverage_pct,
        "covered": report.covered,
        "missing": report.missing,
        "routed_connections": report.routed_connections,
        "unrouted_connections": report.unrouted_connections,
        "routing_ok": report.routing_ok,
        "erc_ok": report.erc_ok,
        "drc_ok": report.drc_ok,
        "constraint_ok": report.constraint_ok,
        "erc_violations": report.erc_violations,
        "drc_violations": report.drc_violations,
    }

    if report.coverage_pct < thresholds.min_coverage_pct:
        failures.append(
            f"Coverage {report.coverage_pct:.1f}% < "
            f"minimum {thresholds.min_coverage_pct:.1f}%"
        )

    if report.unrouted_connections > thresholds.max_unrouted_connections:
        failures.append(
            f"Unrouted connections {report.unrouted_connections} > "
            f"maximum {thresholds.max_unrouted_connections}"
        )

    if thresholds.max_total_route_bends is not None:
        total_bends = sum(e.route_bends for e in report.entries)
        metrics["total_route_bends"] = total_bends
        if total_bends > thresholds.max_total_route_bends:
            failures.append(
                f"Total route bends {total_bends} > "
                f"maximum {thresholds.max_total_route_bends}"
            )

    if thresholds.require_routing_pass and report.routing_ok is False:
        failures.append("Routing failed (unrouted connections present)")

    if thresholds.require_erc_pass and report.erc_ok is False:
        failures.append(
            f"ERC failed ({report.erc_violations} violation(s))"
        )

    if thresholds.require_drc_pass and report.drc_ok is False:
        failures.append(
            f"DRC failed ({report.drc_violations} violation(s))"
        )

    if (
        thresholds.require_constraint_pass
        and report.constraint_ok is False
    ):
        failures.append(
            f"Constraint check failed ({report.constraint_violations} issue(s))"
        )

    if report.erc_violations > thresholds.max_erc_violations:
        failures.append(
            f"ERC violations {report.erc_violations} > "
            f"maximum {thresholds.max_erc_violations}"
        )

    if report.drc_violations > thresholds.max_drc_violations:
        failures.append(
            f"DRC violations {report.drc_violations} > "
            f"maximum {thresholds.max_drc_violations}"
        )

    return QualityGateResult(
        passed=len(failures) == 0,
        failures=failures,
        metrics=metrics,
    )


def load_thresholds_from_json(path: str | Path) -> QualityThresholds:
    """Load thresholds from a JSON file."""
    import json

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    # Filter to only known fields
    known = {f.name for f in QualityThresholds.__dataclass_fields__.values()}
    kwargs = {k: v for k, v in data.items() if k in known}
    return QualityThresholds(**kwargs)
