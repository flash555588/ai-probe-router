"""Tests for native KiCad validation and manufacturing export stages."""

from __future__ import annotations

from pathlib import Path

from ai_probe_router.config import ProjectConfig
from ai_probe_router.eda_adapters.kicad.cli_runner import CheckResult
from ai_probe_router.pipeline import native_tools
from ai_probe_router.pipeline.native_tools import (
    apply_native_validation,
    run_manufacturing_exports,
    run_native_validation,
)
from ai_probe_router.verification.native_validation_runner import NativeValidationRun
from ai_probe_router.verification.report import CoverageReport


def test_run_native_validation_records_available_artifacts(tmp_path: Path, monkeypatch):
    pcb = tmp_path / "main.kicad_pcb"
    sch = tmp_path / "main.kicad_sch"
    pcb.write_text("(kicad_pcb)", encoding="utf-8")
    sch.write_text("(kicad_sch)", encoding="utf-8")
    shared_result = NativeValidationRun(
        return_code=1,
        summary={
            "checks": {
                "drc": {"exit_code": 5, "json_exists": True},
                "erc": {"exit_code": 0, "json_exists": True},
            }
        },
        report_dir=tmp_path / "native_validation",
        findings=[{"source": "drc", "type": "clearance"}],
        grouped_findings=[],
        regression_result={},
    )
    monkeypatch.setattr(
        native_tools,
        "run_shared_native_validation",
        lambda *args, **kwargs: shared_result,
    )

    coverage = CoverageReport()
    result = run_native_validation(pcb, sch, tmp_path)
    apply_native_validation(coverage, result)

    assert coverage.drc_ok is False
    assert coverage.drc_violations == 1
    assert coverage.erc_ok is True
    assert coverage.erc_violations == 0
    assert coverage.notes == ["DRC validation failed: 1 violation(s)"]


def test_native_validation_records_missing_tool_as_soft_note():
    coverage = CoverageReport()
    result = native_tools.NativeValidationResult(
        drc=CheckResult(ok=None, error="kicad-cli not found"),
        erc=CheckResult(ok=None, error="kicad-cli not found"),
    )

    apply_native_validation(coverage, result, ProjectConfig())

    assert coverage.drc_ok is None
    assert coverage.erc_ok is None
    assert coverage.notes == [
        "DRC validation skipped: kicad-cli not found",
        "ERC validation skipped: kicad-cli not found",
    ]


def test_native_validation_strict_signoff_blocks_drc_failure():
    cfg = ProjectConfig()
    cfg.process_controls.strict_signoff = True
    coverage = CoverageReport()
    result = native_tools.NativeValidationResult(
        drc=CheckResult(ok=False, error="drc failed"),
    )

    try:
        apply_native_validation(coverage, result, cfg)
    except RuntimeError as exc:
        assert "DRC validation failed: drc failed" in str(exc)
    else:
        raise AssertionError("strict_signoff should block failed DRC validation")


def test_native_validation_strict_signoff_blocks_missing_kicad():
    cfg = ProjectConfig()
    cfg.process_controls.strict_signoff = True
    coverage = CoverageReport()
    result = native_tools.NativeValidationResult(
        erc=CheckResult(ok=None, error="kicad-cli not found"),
    )

    try:
        apply_native_validation(coverage, result, cfg)
    except RuntimeError as exc:
        assert "ERC validation skipped: kicad-cli not found" in str(exc)
    else:
        raise AssertionError("strict_signoff should block missing native KiCad")


def test_run_native_validation_skips_missing_artifacts(tmp_path: Path, monkeypatch):
    calls = []
    shared_result = NativeValidationRun(
        return_code=0,
        summary={"checks": {}},
        report_dir=tmp_path / "native_validation",
        findings=[],
        grouped_findings=[],
        regression_result={},
    )

    def fake_shared_runner(*args, **kwargs):
        calls.append(args)
        return shared_result

    monkeypatch.setattr(native_tools, "run_shared_native_validation", fake_shared_runner)

    result = run_native_validation(tmp_path / "missing.kicad_pcb", None, tmp_path)

    assert result.drc is None
    assert result.erc is None
    assert len(calls) == 1


def test_manufacturing_exports_record_success_notes(tmp_path: Path, monkeypatch):
    pcb = tmp_path / "main.kicad_pcb"
    pcb.write_text("(kicad_pcb)", encoding="utf-8")
    ok = CheckResult(ok=True)
    monkeypatch.setattr(native_tools, "export_gerbers", lambda *args: ok)
    monkeypatch.setattr(native_tools, "export_drill", lambda *args: ok)
    monkeypatch.setattr(native_tools, "export_pos", lambda *args: ok)

    coverage = CoverageReport()
    statuses = run_manufacturing_exports(ProjectConfig(), coverage, pcb, tmp_path / "mfg")

    assert [status.label for status in statuses] == ["Gerber", "Drill", "Pick&Place"]
    assert all(status.ok for status in statuses)
    assert coverage.notes == [
        "Gerber files exported",
        "Drill files exported",
        "Pick&Place file exported",
    ]


def test_manufacturing_exports_record_soft_failures(tmp_path: Path, monkeypatch):
    pcb = tmp_path / "main.kicad_pcb"
    pcb.write_text("(kicad_pcb)", encoding="utf-8")
    failed = CheckResult(ok=None, error="kicad-cli not found")
    monkeypatch.setattr(native_tools, "export_gerbers", lambda *args: failed)
    monkeypatch.setattr(native_tools, "export_drill", lambda *args: failed)
    monkeypatch.setattr(native_tools, "export_pos", lambda *args: failed)

    coverage = CoverageReport()
    statuses = run_manufacturing_exports(ProjectConfig(), coverage, pcb, tmp_path / "mfg")

    assert [status.ok for status in statuses] == [None, None, None]
    assert coverage.notes == [
        "Gerber export failed: kicad-cli not found",
        "Drill export failed: kicad-cli not found",
        "Pick&Place export failed: kicad-cli not found",
    ]


def test_manufacturing_exports_strict_signoff_blocks_failure(tmp_path: Path, monkeypatch):
    pcb = tmp_path / "main.kicad_pcb"
    pcb.write_text("(kicad_pcb)", encoding="utf-8")
    monkeypatch.setattr(
        native_tools,
        "export_gerbers",
        lambda *args: CheckResult(ok=False, error="gerber failed"),
    )

    cfg = ProjectConfig()
    cfg.process_controls.strict_signoff = True
    coverage = CoverageReport()

    try:
        run_manufacturing_exports(cfg, coverage, pcb, tmp_path / "mfg")
    except RuntimeError as exc:
        assert "Gerber export failed: gerber failed" in str(exc)
    else:
        raise AssertionError("strict_signoff should block failed Gerber export")


def test_manufacturing_exports_required_exports_block_failure(tmp_path: Path, monkeypatch):
    pcb = tmp_path / "main.kicad_pcb"
    pcb.write_text("(kicad_pcb)", encoding="utf-8")
    monkeypatch.setattr(
        native_tools,
        "export_gerbers",
        lambda *args: CheckResult(ok=False, error="gerber failed"),
    )

    cfg = ProjectConfig()
    cfg.process_controls.require_manufacturing_exports = True
    coverage = CoverageReport()

    try:
        run_manufacturing_exports(cfg, coverage, pcb, tmp_path / "mfg")
    except RuntimeError as exc:
        assert "Gerber export failed: gerber failed" in str(exc)
    else:
        raise AssertionError("required manufacturing exports should block failed export")
