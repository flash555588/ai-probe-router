"""Tests for manufacturing readiness report."""

from ai_probe_router.models.board import Board, EdgeSegment
from ai_probe_router.models.net import NetRole
from ai_probe_router.verification.manufacturing_report import (
    ManufacturingReport,
    generate_manufacturing_report,
)
from ai_probe_router.verification.report import CoverageReport, NetCoverage


def test_empty_manufacturing_report():
    report = ManufacturingReport()
    assert report.board_outline_ok is False
    assert report.testpoint_coverage_pct == 0.0
    assert "MISSING" in report.summary_text()


def test_manufacturing_report_with_data():
    report = ManufacturingReport(
        board_outline_ok=True,
        board_size_mm=(50.0, 30.0),
        testpoint_coverage_pct=100.0,
        fiducial_count=3,
        tooling_hole_count=2,
        keepout_zone_count=5,
        review_gate_count=0,
    )
    text = report.summary_text()
    assert "50.0 x 30.0" in text
    assert "100.0%" in text
    assert "Fiducials:         3" in text
    assert "Manufacturing ready: YES" in text


def test_manufacturing_not_ready_with_review_gates():
    report = ManufacturingReport(
        board_outline_ok=True,
        testpoint_coverage_pct=100.0,
        review_gate_count=1,
    )
    assert "Manufacturing ready: NO" in report.summary_text()


def test_generate_from_coverage():
    coverage = CoverageReport(total_nets_requested=2, covered=2, missing=0)
    coverage.entries = [
        NetCoverage("SWDIO", NetRole.DEBUG, True, True, review_required=False),
        NetCoverage("USB_DP", NetRole.HIGH_SPEED, True, True, review_required=True),
    ]
    board = Board(
        raw=["kicad_pcb"],
        nets={},
        footprints=[],
        edges=[
            EdgeSegment(0, 0, 40, 0),
            EdgeSegment(40, 0, 40, 40),
            EdgeSegment(40, 40, 0, 40),
            EdgeSegment(0, 40, 0, 0),
        ],
    )
    mfg = generate_manufacturing_report(board, coverage)
    assert mfg.board_outline_ok is True
    assert abs(mfg.board_size_mm[0] - 40.0) < 0.01
    assert mfg.testpoint_coverage_pct == 100.0
    assert mfg.review_gate_count == 1
    assert mfg.net_class_summary.get("DEBUG", 0) == 1
    assert mfg.net_class_summary.get("HIGH_SPEED", 0) == 1


def test_generate_no_board():
    coverage = CoverageReport(total_nets_requested=1, covered=1)
    coverage.entries = [NetCoverage("GND", NetRole.GROUND, True, True)]
    mfg = generate_manufacturing_report(None, coverage)
    assert mfg.board_outline_ok is False
    assert mfg.testpoint_coverage_pct == 100.0


def test_manufacturing_report_write(tmp_path):
    report = ManufacturingReport(board_outline_ok=True, testpoint_coverage_pct=100.0)
    path = tmp_path / "mfg.txt"
    report.write(path)
    assert path.exists()
    assert "Manufacturing ready: YES" in path.read_text(encoding="utf-8")
