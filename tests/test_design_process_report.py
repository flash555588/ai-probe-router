import json

from ai_probe_router.config import ProjectConfig
from ai_probe_router.models.net import NetRole
from ai_probe_router.models.probe import ProbeRequirement
from ai_probe_router.models.process_control import ProcessWaiver
from ai_probe_router.verification.decision_manifest import (
    collect_artifact_manifest,
    write_decision_manifest,
)
from ai_probe_router.verification.design_process_report import (
    DesignProcessReport,
    ProcessIssue,
    generate_design_process_report,
)
from ai_probe_router.verification.diff_pair_skew_report import (
    DiffPairSkewReport,
    DiffPairSkewRow,
)
from ai_probe_router.verification.readiness_report import generate_readiness_report
from ai_probe_router.verification.report import CoverageReport, NetCoverage


def test_design_process_report_marks_waived_issue():
    cfg = ProjectConfig(
        nets_to_expose=[
            ProbeRequirement(
                net_name="USB_DP",
                role="high_speed",
                pair_net_name="USB_DM",
            ),
        ],
    )
    cfg.process_controls.waivers = [
        ProcessWaiver(
            waiver_id="WV-1",
            source="electrical_signoff",
            issue_id="electrical_review_required",
            owner="layout-review",
            reason="Reviewed against external USB layout checklist",
        ),
    ]
    coverage = CoverageReport(
        entries=[
            NetCoverage(
                "USB_DP",
                NetRole.HIGH_SPEED,
                required=True,
                has_testpoint=True,
                review_required=True,
            ),
        ],
    )
    diff_pair = DiffPairSkewReport(
        pairs=[
            DiffPairSkewRow("USB_DP", "USB_DM", 10.0, 10.1, -0.1, -1.0, True),
        ],
    )

    report = generate_design_process_report(
        cfg,
        run_id="APR-TEST",
        coverage=coverage,
        diff_pair_report=diff_pair,
    )

    assert any(issue.waiver_id == "WV-1" for issue in report.waived_issues)
    assert "electrical_review_required" in report.summary_text()


def test_strict_process_report_escalates_open_warnings():
    cfg = ProjectConfig()
    cfg.process_controls.strict_signoff = True
    coverage = CoverageReport()

    report = generate_design_process_report(cfg, coverage=coverage)

    assert report.open_errors
    assert any(issue.source == "manufacturing_dfm" for issue in report.open_errors)


def test_readiness_includes_process_report():
    coverage = CoverageReport(total_nets_requested=0)
    process = DesignProcessReport(
        issues=[
            ProcessIssue(
                "warning",
                "fixture_realism",
                "fixture_tooling_not_required",
                "tooling holes are not required",
            ),
            ProcessIssue(
                "warning",
                "electrical_signoff",
                "electrical_review_required",
                "external checklist approved",
                status="waived",
                waiver_id="WV-1",
            ),
        ],
    )

    readiness = generate_readiness_report(coverage, process_report=process)

    assert readiness.verdict == "PASS_WITH_REVIEW"
    assert any(issue.source == "process:fixture_realism" for issue in readiness.warnings)
    assert any("waived by WV-1" in issue.message for issue in readiness.infos)


def test_decision_manifest_records_artifacts_and_diff(tmp_path):
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    (out_dir / "design_process_report.txt").write_text("process", encoding="utf-8")
    artifacts = collect_artifact_manifest(out_dir)
    coverage = CoverageReport(run_id="APR-TEST")
    readiness = generate_readiness_report(coverage)
    process = DesignProcessReport(run_id="APR-TEST")

    manifest = write_decision_manifest(
        out_dir / "decision_manifest.json",
        run_id="APR-TEST",
        cfg=ProjectConfig(),
        coverage=coverage,
        readiness_report=readiness,
        process_report=process,
        prior_manifest={"run_id": "APR-OLD", "modules": []},
        artifacts=artifacts,
    )

    raw = json.loads((out_dir / "decision_manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == "APR-TEST"
    assert raw["change_summary"]["previous_run_id"] == "APR-OLD"
    assert raw["change_summary"]["run_id_changed"]
    assert raw["artifacts"][0]["path"] == "design_process_report.txt"
