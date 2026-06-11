"""Tests for quality_gate metric-based assertions."""

from ai_probe_router.models.net import NetRole
from ai_probe_router.verification.quality_gate import QualityThresholds, check_quality_gate
from ai_probe_router.verification.report import CoverageReport, NetCoverage


def test_gate_passes_with_perfect_coverage():
    report = CoverageReport(total_nets_requested=2, covered=2, missing=0)
    report.routing_ok = True
    report.routed_connections = 2
    report.unrouted_connections = 0
    result = check_quality_gate(report)
    assert result.passed is True
    assert result.failures == []


def test_gate_fails_low_coverage():
    report = CoverageReport(total_nets_requested=2, covered=1, missing=1)
    report.routing_ok = True
    result = check_quality_gate(report)
    assert result.passed is False
    assert any("Coverage" in f for f in result.failures)


def test_gate_fails_unrouted_connections():
    report = CoverageReport(total_nets_requested=1, covered=1, missing=0)
    report.routing_ok = False
    report.routed_connections = 0
    report.unrouted_connections = 1
    result = check_quality_gate(report)
    assert result.passed is False
    assert any("Unrouted" in f for f in result.failures)


def test_gate_fails_routing_ok_false():
    report = CoverageReport(total_nets_requested=1, covered=1, missing=0)
    report.routing_ok = False
    report.routed_connections = 0
    report.unrouted_connections = 1
    result = check_quality_gate(report, QualityThresholds(require_routing_pass=True))
    assert result.passed is False
    assert any("Routing failed" in f for f in result.failures)


def test_gate_ignores_routing_when_not_required():
    report = CoverageReport(total_nets_requested=1, covered=1, missing=0)
    report.routing_ok = False
    report.routed_connections = 0
    report.unrouted_connections = 1
    result = check_quality_gate(
        report, QualityThresholds(require_routing_pass=False, max_unrouted_connections=5)
    )
    assert result.passed is True


def test_gate_fails_erc():
    report = CoverageReport(total_nets_requested=1, covered=1, missing=0)
    report.routing_ok = True
    report.erc_ok = False
    report.erc_violations = 3
    result = check_quality_gate(report, QualityThresholds(require_erc_pass=True))
    assert result.passed is False
    assert any("ERC" in f for f in result.failures)


def test_gate_fails_drc():
    report = CoverageReport(total_nets_requested=1, covered=1, missing=0)
    report.routing_ok = True
    report.drc_ok = False
    report.drc_violations = 2
    result = check_quality_gate(report, QualityThresholds(require_drc_pass=True))
    assert result.passed is False
    assert any("DRC" in f for f in result.failures)


def test_gate_fails_too_many_bends():
    report = CoverageReport(total_nets_requested=1, covered=1, missing=0)
    report.routing_ok = True
    report.entries.append(
        NetCoverage(
            net_name="SIG",
            role=NetRole.GPIO,
            required=True,
            has_testpoint=True,
            route_bends=10,
        )
    )
    result = check_quality_gate(report, QualityThresholds(max_total_route_bends=5))
    assert result.passed is False
    assert any("bends" in f.lower() for f in result.failures)


def test_gate_passes_bends_within_limit():
    report = CoverageReport(total_nets_requested=1, covered=1, missing=0)
    report.routing_ok = True
    report.entries.append(
        NetCoverage(
            net_name="SIG",
            role=NetRole.GPIO,
            required=True,
            has_testpoint=True,
            route_bends=3,
        )
    )
    result = check_quality_gate(report, QualityThresholds(max_total_route_bends=5))
    assert result.passed is True


def test_gate_ignores_null_routing_ok_when_not_required():
    report = CoverageReport(total_nets_requested=1, covered=1, missing=0)
    report.routing_ok = None
    result = check_quality_gate(report, QualityThresholds(require_routing_pass=True))
    assert result.passed is True


def test_metrics_populated():
    report = CoverageReport(total_nets_requested=2, covered=2, missing=0)
    report.routing_ok = True
    report.routed_connections = 2
    report.unrouted_connections = 0
    result = check_quality_gate(report)
    assert result.metrics["coverage_pct"] == 100.0
    assert result.metrics["routed_connections"] == 2
    assert result.metrics["unrouted_connections"] == 0
