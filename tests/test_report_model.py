"""Tests for PluginReportModel merged view."""

from ai_probe_router.report_utils import UnifiedReports
from ai_probe_router.ui.report_loader import (
    FootprintEntry,
    FootprintPreviewData,
    IssueEntry,
    ReadinessData,
    ReadinessIssue,
    ResourceAllocationData,
    ResourceBusEntry,
)
from ai_probe_router.ui.report_model import PluginReportModel


def _make_reports() -> UnifiedReports:
    fp = FootprintPreviewData(
        ok=True,
        has_warnings=False,
        footprints=[
            FootprintEntry(
                module_name="power_monitor",
                reference="U101",
                footprint="fp",
                x_mm=10.0,
                y_mm=20.0,
                rotation_deg=0.0,
                side="top",
                role="mcu",
            )
        ],
        issues=[
            IssueEntry(
                severity="error",
                code="COLLISION",
                message="collides",
                module_name="power_monitor",
                reference="U101",
            )
        ],
    )
    ra = ResourceAllocationData(
        ok=True,
        warnings=[],
        errors=[],
        buses=[
            ResourceBusEntry(
                bus_type="i2c",
                bus_id=1,
                module="power_monitor",
                instance_id="U101",
                address="0x50",
            )
        ],
        power=[],
    )
    rd = ReadinessData(
        verdict="PASS_WITH_REVIEW",
        run_id="APR-TEST",
        blockers=[],
        warnings=[
            ReadinessIssue(
                severity="warning",
                source="footprint_preview",
                message="dense region",
            )
        ],
    )
    return UnifiedReports(
        output_dir=None,
        footprint_preview=fp,
        resource_allocation=ra,
        readiness=rd,
    )


class TestPluginReportModel:
    def test_module_summary_finds_footprint(self):
        model = PluginReportModel(_make_reports())
        summary = model.module_summary("power_monitor", "U101")
        assert summary.module_name == "power_monitor"
        assert summary.reference == "U101"
        assert summary.footprint == "fp"

    def test_module_summary_severity_from_footprint_issues(self):
        model = PluginReportModel(_make_reports())
        summary = model.module_summary("power_monitor", "U101")
        assert summary.severity == "error"
        assert len(summary.footprint_issues) == 1
        assert summary.footprint_issues[0]["code"] == "COLLISION"

    def test_module_summary_resource_assignments(self):
        model = PluginReportModel(_make_reports())
        summary = model.module_summary("power_monitor", "U101")
        assert len(summary.resource_assignments) == 1
        assert summary.resource_assignments[0]["bus_type"] == "i2c"

    def test_module_summary_readiness_codes(self):
        model = PluginReportModel(_make_reports())
        summary = model.module_summary("power_monitor")
        assert len(summary.readiness_codes) == 1
        assert "dense region" in summary.readiness_codes

    def test_module_summary_unknown_module(self):
        model = PluginReportModel(_make_reports())
        summary = model.module_summary("unknown")
        assert summary.footprint is None
        assert summary.severity == "info"
