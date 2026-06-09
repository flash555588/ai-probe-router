"""Tests for the delivery artifact writing pipeline stage."""

from __future__ import annotations

import json
from pathlib import Path

from ai_probe_router.config import ProjectConfig
from ai_probe_router.models.net import NetRole
from ai_probe_router.pipeline.delivery_artifacts import write_delivery_artifacts
from ai_probe_router.routing.freerouting_bridge import RoutingResult
from ai_probe_router.verification.manufacturing_report import ManufacturingReport
from ai_probe_router.verification.report import CoverageReport, NetCoverage


def test_delivery_artifacts_write_reports_and_manifest(tmp_path: Path):
    cfg = ProjectConfig(board_file="main.kicad_pcb", schematic_file="main.kicad_sch")
    coverage = CoverageReport(
        run_id="APR-DELIVERY",
        total_nets_requested=1,
        covered=1,
        entries=[
            NetCoverage(
                net_name="SWDIO",
                role=NetRole.DEBUG,
                required=True,
                has_testpoint=True,
            ),
        ],
        notes=["DRC validation skipped: kicad-cli not found"],
    )
    manufacturing = ManufacturingReport(
        board_outline_ok=True,
        testpoint_coverage_pct=100.0,
    )
    (tmp_path / "main.kicad_pcb").write_text("pcb", encoding="utf-8")

    result = write_delivery_artifacts(
        out_dir=tmp_path,
        cfg=cfg,
        run_id="APR-DELIVERY",
        board=None,
        coverage=coverage,
        manufacturing_report=manufacturing,
        autoroute_result=RoutingResult(error="FreeRouting not found"),
    )

    assert (tmp_path / "design_process_report.txt").is_file()
    assert (tmp_path / "testpoint_report.txt").is_file()
    assert (tmp_path / "readiness_report.txt").is_file()
    assert (tmp_path / "decision_manifest.json").is_file()
    assert result.readiness_report.verdict == "PASS_WITH_REVIEW"
    assert result.manifest["run_id"] == "APR-DELIVERY"
    assert result.manifest["coverage"]["covered"] == 1
    assert result.manifest["artifacts"]
    assert "decision_manifest.json" not in {
        artifact["path"] for artifact in result.manifest["artifacts"]
    }
    manifest = json.loads((tmp_path / "decision_manifest.json").read_text(encoding="utf-8"))
    assert manifest == result.manifest


def test_delivery_artifacts_include_prior_manifest_diff(tmp_path: Path):
    cfg = ProjectConfig()
    coverage = CoverageReport(run_id="APR-NEW")
    manufacturing = ManufacturingReport()

    result = write_delivery_artifacts(
        out_dir=tmp_path,
        cfg=cfg,
        run_id="APR-NEW",
        board=None,
        coverage=coverage,
        manufacturing_report=manufacturing,
        prior_manifest={"run_id": "APR-OLD"},
    )

    process_text = (tmp_path / "design_process_report.txt").read_text(encoding="utf-8")
    assert result.process_report.prior_run_id == "APR-OLD"
    assert "Prior Run ID:  APR-OLD" in process_text
    assert result.manifest["change_summary"]["previous_run_id"] == "APR-OLD"
