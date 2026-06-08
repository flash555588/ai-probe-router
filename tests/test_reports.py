"""Tests for verification reports."""

from ai_probe_router.models.net import NetRole
from ai_probe_router.solvers.pin_mapper import MappingResult, PinAssignment
from ai_probe_router.verification.pin_report import PinMapReport
from ai_probe_router.verification.report import CoverageReport, NetCoverage


def test_coverage_report_pct():
    report = CoverageReport(total_nets_requested=10, covered=7, missing=3)
    assert abs(report.coverage_pct - 70.0) < 0.01


def test_coverage_report_pct_zero():
    report = CoverageReport(total_nets_requested=0, covered=0, missing=0)
    assert report.coverage_pct == 100.0


def test_coverage_report_summary_text():
    report = CoverageReport(
        run_id="APR-TEST",
        total_nets_requested=2, covered=2, missing=0,
        entries=[
            NetCoverage("SWDIO", NetRole.DEBUG, True, True, 110, 100, "top"),
            NetCoverage("GND", NetRole.GROUND, True, True, 115, 100, "top"),
        ],
        drc_ok=True, erc_ok=True,
    )
    text = report.summary_text()
    assert "APR-TEST" in text
    assert "100.0%" in text
    assert "SWDIO" in text
    assert "PASS" in text


def test_coverage_report_with_constraints():
    report = CoverageReport(
        total_nets_requested=1, covered=1, missing=0,
        constraint_ok=False, constraint_violations=2,
        constraint_messages=["too close to edge", "spacing violation"],
    )
    text = report.summary_text()
    assert "FAIL" in text
    assert "too close to edge" in text


def test_coverage_report_separates_placement_from_routing():
    report = CoverageReport(
        total_nets_requested=1,
        covered=1,
        missing=0,
        routing_ok=False,
        routed_connections=0,
        unrouted_connections=1,
        entries=[
            NetCoverage(
                "UART_TX",
                NetRole.COMMUNICATION,
                True,
                True,
                12.0,
                18.0,
                "top",
                route_status="unrouted",
                routed_connections=0,
                total_connections=1,
                routing_notes=["grid_route_not_found"],
            ),
        ],
    )
    text = report.summary_text()
    assert "Routing:          UNROUTED (0/1 connections)" in text
    assert "YES      0/1" in text
    assert "grid_route_not_found" in text


def test_coverage_report_write(tmp_path):
    report = CoverageReport(total_nets_requested=1, covered=1, missing=0)
    report.entries.append(NetCoverage("GND", NetRole.GROUND, True, True))
    path = tmp_path / "report.txt"
    report.write(path)
    assert path.exists()
    assert "GND" in path.read_text(encoding="utf-8")


def test_pin_map_report():
    result = MappingResult(
        assignments=[
            PinAssignment("SWDIO", "PA13", 0, 110.0),
            PinAssignment("SWCLK", "PA14", 1, 110.0),
        ],
    )
    report = PinMapReport(board_name="test_board", result=result)
    text = report.summary_text()
    assert "test_board" in text
    assert "SWDIO" in text
    assert "PA13" in text
    assert "Assigned:          2" in text


def test_pin_map_report_with_errors():
    result = MappingResult(
        assignments=[],
        errors=["No pin found for USB_DP"],
    )
    report = PinMapReport(board_name="test_board", result=result)
    text = report.summary_text()
    assert "Errors:" in text
    assert "USB_DP" in text


def test_pin_map_report_write(tmp_path):
    result = MappingResult(
        assignments=[PinAssignment("GND", "GND_1", 0, 60.0)],
    )
    report = PinMapReport(board_name="test", result=result)
    path = tmp_path / "pin_report.txt"
    report.write(path)
    assert path.exists()
    assert "GND" in path.read_text(encoding="utf-8")
