from ai_probe_router.models.module_graph import ModuleGraphResult
from ai_probe_router.models.net import NetRole
from ai_probe_router.verification.manufacturing_report import ManufacturingReport
from ai_probe_router.verification.readiness_report import generate_readiness_report
from ai_probe_router.verification.report import CoverageReport, NetCoverage


def test_readiness_passes_clean_run():
    coverage = CoverageReport(
        run_id="APR-COVERAGE",
        total_nets_requested=1,
        covered=1,
        missing=0,
        entries=[NetCoverage("GND", NetRole.GROUND, True, True)],
        constraint_ok=True,
        drc_ok=True,
        erc_ok=True,
    )
    mfg = ManufacturingReport(
        board_outline_ok=True,
        testpoint_coverage_pct=100.0,
    )

    report = generate_readiness_report(coverage, manufacturing_report=mfg)

    assert report.verdict == "PASS"
    assert "APR-COVERAGE" in report.summary_text()
    assert "No blocking" in report.summary_text()


def test_readiness_accepts_explicit_run_id():
    coverage = CoverageReport(run_id="APR-COVERAGE")

    report = generate_readiness_report(coverage, run_id="APR-EXPLICIT")

    text = report.summary_text()
    assert report.run_id == "APR-EXPLICIT"
    assert "APR-EXPLICIT" in text


def test_readiness_blocks_module_graph_error():
    coverage = CoverageReport()
    graph = ModuleGraphResult(errors=["MOD1/debug depends on missing module 'power'"])

    report = generate_readiness_report(coverage, module_graph_result=graph)

    assert report.verdict == "BLOCKED"
    assert report.blockers[0].source == "module_graph"


def test_readiness_marks_review_for_skipped_manufacturing_context():
    coverage = CoverageReport(
        total_nets_requested=1,
        covered=1,
        missing=0,
        entries=[
            NetCoverage(
                "ADC_IN",
                NetRole.ANALOG,
                True,
                True,
                review_required=True,
            ),
        ],
    )
    mfg = ManufacturingReport(board_outline_ok=False, testpoint_coverage_pct=100.0)

    report = generate_readiness_report(coverage, manufacturing_report=mfg)

    assert report.verdict == "PASS_WITH_REVIEW"
    assert any(issue.source == "human_review" for issue in report.warnings)
