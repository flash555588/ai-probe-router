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
    testpoint_report = (out_dir / "testpoint_report.txt").read_text(encoding="utf-8")

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
    assert "version" in manifest["native_tools"]["kicad_cli"]
    assert "version_error" in manifest["native_tools"]["kicad_cli"]
    assert isinstance(manifest["coverage"]["notes"], list)
    for note in manifest["coverage"]["notes"]:
        assert note in testpoint_report
    if manifest["coverage"]["notes"]:
        assert "Notes:" in testpoint_report

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


def test_audio_player_generation_reaches_semantic_module_planning(tmp_path: Path):
    repo_root = Path(__file__).parent.parent
    project_src = repo_root / "examples" / "audio_player_project"

    shutil.copy(project_src / "main.kicad_pcb", tmp_path / "main.kicad_pcb")
    shutil.copy(project_src / "main.kicad_sch", tmp_path / "main.kicad_sch")
    shutil.copy(project_src / "audio_player_config.yaml", tmp_path / "config.yaml")

    cfg = load_config(tmp_path / "config.yaml")
    coverage, pin_report = run(cfg, tmp_path)

    out_dir = tmp_path / "output"
    manifest = json.loads((out_dir / "decision_manifest.json").read_text(encoding="utf-8"))
    preflight = (out_dir / "module_library_preflight_report.txt").read_text(
        encoding="utf-8",
    )
    resource = json.loads((out_dir / "resource_allocation_report.json").read_text(
        encoding="utf-8",
    ))

    expected_modules = {module.name for module in cfg.functional_modules}
    planned_modules = {module["name"] for module in manifest["modules"]}

    assert pin_report is None
    assert coverage.notes == [
        "Module planning blocked generation; no PCB or schematic changes were written",
    ]
    assert "requested module type" not in preflight
    assert expected_modules == planned_modules
    assert manifest["readiness"]["verdict"] == "BLOCKED"
    assert manifest["readiness"]["blockers"] > 0
    assert manifest["coverage"]["notes"] == coverage.notes
    assert manifest["routing"]["corridors"] == []
    assert not resource["ok"]
    assert "POWER_DOMAIN_OVERLOAD" in resource["errors"]
    assert not (out_dir / "main.kicad_pcb").exists()


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
    monkeypatch.setattr(decision_manifest, "find_freerouting", lambda: None)
    monkeypatch.setattr(
        decision_manifest,
        "_probe_version",
        lambda cmd, stderr_version=False: (" ".join(cmd), ""),
    )

    path = tmp_path / "decision_manifest.json"
    write_decision_manifest(
        path,
        run_id="APR-TEST",
        cfg=load_config(Path(__file__).parent.parent / "examples" / "sample_config.yaml"),
        coverage=CoverageReport(
            total_nets_requested=0,
            covered=0,
            missing=0,
            notes=["DRC validation skipped: kicad-cli not found"],
        ),
        readiness_report=ReadinessReport(run_id="APR-TEST"),
        process_report=DesignProcessReport(run_id="APR-TEST"),
        artifacts=[],
    )

    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["native_tools"]["kicad_cli"]["available"] is True
    assert manifest["native_tools"]["kicad_cli"]["path"] == "/usr/bin/kicad-cli"
    assert manifest["native_tools"]["kicad_cli"]["version"] == "kicad-cli version"
    assert manifest["native_tools"]["java"]["available"] is True
    assert manifest["native_tools"]["java"]["version"] == "java -version"
    assert manifest["native_tools"]["freerouting"]["available"] is False
    assert manifest["native_tools"]["freerouting"]["path"] == ""
    assert "version" in manifest["native_tools"]["freerouting"]
    assert manifest["coverage"]["notes"] == [
        "DRC validation skipped: kicad-cli not found",
    ]


def test_decision_manifest_records_freerouting_jar_java_dependency(
    tmp_path: Path,
    monkeypatch,
):
    from ai_probe_router.verification import decision_manifest
    from ai_probe_router.verification.decision_manifest import write_decision_manifest
    from ai_probe_router.verification.design_process_report import DesignProcessReport
    from ai_probe_router.verification.readiness_report import ReadinessReport
    from ai_probe_router.verification.report import CoverageReport

    jar_path = tmp_path / "freerouting.jar"
    jar_path.write_text("jar", encoding="utf-8")
    monkeypatch.setattr(decision_manifest, "find_freerouting", lambda: str(jar_path))
    monkeypatch.setattr(decision_manifest.shutil, "which", lambda name: None)

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
    freerouting = manifest["native_tools"]["freerouting"]
    assert freerouting["available"] is True
    assert freerouting["path"] == str(jar_path)
    assert freerouting["kind"] == "jar"
    assert freerouting["java_available"] is False
    assert freerouting["version_error"] == "java not found in PATH"
