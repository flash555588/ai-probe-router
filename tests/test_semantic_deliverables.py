"""Semantic checks for generated deliverables beyond file existence."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from ai_probe_router.config import load_config
from ai_probe_router.eda_adapters.kicad.pcb_parser import parse_pcb
from ai_probe_router.engine import run
from ai_probe_router.models.net import NetRole


def test_sample_generation_preserves_expected_probe_semantics(tmp_path: Path):
    repo_root = Path(__file__).parent.parent
    examples = repo_root / "examples"
    project_src = examples / "minimal_project"
    config_src = examples / "sample_config.yaml"

    shutil.copy(project_src / "main.kicad_pcb", tmp_path / "main.kicad_pcb")
    shutil.copy(project_src / "main.kicad_sch", tmp_path / "main.kicad_sch")
    shutil.copy(config_src, tmp_path / "config.yaml")

    cfg = load_config(tmp_path / "config.yaml")
    coverage, _ = run(cfg, tmp_path)

    out_dir = tmp_path / "output"
    board = parse_pcb(out_dir / "main.kicad_pcb")
    generated_pcb = (out_dir / "main.kicad_pcb").read_text(encoding="utf-8")
    generated_sch = (out_dir / "main.kicad_sch").read_text(encoding="utf-8")
    manifest = json.loads((out_dir / "decision_manifest.json").read_text(encoding="utf-8"))
    readiness = (out_dir / "readiness_report.txt").read_text(encoding="utf-8")

    expected_nets = {req.net_name for req in cfg.nets_to_expose}
    required_nets = {req.net_name for req in cfg.nets_to_expose if req.required}
    covered_nets = {entry.net_name for entry in coverage.entries if entry.has_testpoint}
    probe_refs = {entry.net_name: f"TP{index}" for index, entry in enumerate(coverage.entries, 1)}

    assert {entry.net_name for entry in coverage.entries} == expected_nets
    assert manifest["coverage"]["requested"] == len(expected_nets)
    assert manifest["coverage"]["covered"] == coverage.covered
    assert manifest["coverage"]["missing"] == coverage.missing
    assert required_nets <= covered_nets
    assert manifest["readiness"]["verdict"] == "PASS_WITH_REVIEW"
    assert isinstance(manifest["native_tools"]["kicad_cli"]["available"], bool)
    assert "path" in manifest["native_tools"]["kicad_cli"]

    for net_name in covered_nets:
        assert net_name in board.nets
        assert f'NET_{net_name}' in generated_pcb
        if f"PROBE_{net_name}" in generated_pcb:
            assert f"PROBE_{net_name}" in generated_sch
        else:
            assert f'(label "{net_name}"' in generated_sch
        assert probe_refs[net_name] in generated_pcb

    debug_entry = next(entry for entry in coverage.entries if entry.net_name == "SWDIO")
    power_entry = next(entry for entry in coverage.entries if entry.net_name == "3V3")
    assert debug_entry.role is NetRole.DEBUG
    assert power_entry.role is NetRole.POWER
    assert power_entry.trace_width_mm >= cfg.constraints.manufacturing.min_trace_width_mm
    assert 'net_class "NET_3V3"' in generated_pcb
    assert "manufacturing" in readiness


def test_decision_manifest_records_native_tool_presence(tmp_path: Path, monkeypatch):
    from ai_probe_router.verification import decision_manifest
    from ai_probe_router.verification.decision_manifest import write_decision_manifest
    from ai_probe_router.verification.design_process_report import DesignProcessReport
    from ai_probe_router.verification.readiness_report import ReadinessReport
    from ai_probe_router.verification.report import CoverageReport

    monkeypatch.setattr(
        decision_manifest.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name in {"kicad-cli", "java"} else None,
    )

    path = tmp_path / "decision_manifest.json"
    write_decision_manifest(
        path,
        run_id="APR-TEST",
        cfg=load_config(Path(__file__).parent.parent / "examples" / "sample_config.yaml"),
        coverage=CoverageReport(total_nets_requested=0, covered=0, missing=0),
        readiness_report=ReadinessReport(run_id="APR-TEST"),
        process_report=DesignProcessReport(run_id="APR-TEST"),
        artifacts=[],
    )

    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["native_tools"]["kicad_cli"] == {
        "available": True,
        "path": "/usr/bin/kicad-cli",
    }
    assert manifest["native_tools"]["java"]["available"] is True
    assert manifest["native_tools"]["freerouting"] == {"available": False, "path": ""}
