"""Tests for the CLI entry point."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from ai_probe_router.cli import main
from ai_probe_router.models.net import NetRole
from ai_probe_router.verification.readiness_report import ReadinessReport
from ai_probe_router.verification.report import CoverageReport, NetCoverage


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_help(runner: CliRunner):
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "generate" in result.output
    assert "inspect" in result.output
    assert "validate" in result.output


def test_cli_version(runner: CliRunner):
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "1.0.0" in result.output


def test_inspect_pcb(runner: CliRunner):
    pcb = Path(__file__).parent.parent / "examples" / "minimal_project" / "main.kicad_pcb"
    result = runner.invoke(main, ["inspect", str(pcb)])
    assert result.exit_code == 0
    assert "GND" in result.output
    assert "3V3" in result.output
    assert "Total nets:" in result.output


def test_inspect_sch(runner: CliRunner):
    sch = Path(__file__).parent.parent / "examples" / "minimal_project" / "main.kicad_sch"
    result = runner.invoke(main, ["inspect-sch", str(sch)])
    assert result.exit_code == 0
    assert "Components:" in result.output
    assert "Wires:" in result.output


def test_validate_no_testpoints(runner: CliRunner):
    pcb = Path(__file__).parent.parent / "examples" / "minimal_project" / "main.kicad_pcb"
    result = runner.invoke(main, ["validate", str(pcb)])
    assert result.exit_code == 0
    assert "No testpoints found" in result.output


def test_generate(runner: CliRunner, tmp_path: Path):
    src_dir = Path(__file__).parent.parent / "examples" / "minimal_project"
    dst = tmp_path / "project"
    dst.mkdir()
    shutil.copy(src_dir / "main.kicad_pcb", dst / "main.kicad_pcb")
    shutil.copy(src_dir / "main.kicad_sch", dst / "main.kicad_sch")

    config = """\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

probe_interface:
  type: test_pad
  side: top
  pad_diameter_mm: 1.5
  min_probe_spacing_mm: 2.54
  preferred_grid_mm: 2.54
  require_silkscreen_labels: false
  require_fiducials: false
  require_tooling_holes: false

nets_to_expose:
  - net: GND
    role: ground
    required: true
  - net: SWDIO
    role: debug
    required: true
"""
    cfg_path = dst / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")

    result = runner.invoke(main, ["generate", str(cfg_path), "-d", str(dst)])
    assert result.exit_code == 2, result.output
    assert "Coverage:" in result.output
    assert "Readiness: PASS_WITH_REVIEW" in result.output
    assert "GND" in result.output
    assert "SWDIO" in result.output

    out_dir = dst / "output"
    assert out_dir.exists()
    assert (out_dir / "main.kicad_pcb").exists()
    assert (out_dir / "testpoint_report.txt").exists()
    assert (out_dir / "readiness_report.json").exists()


def test_generate_no_sch(runner: CliRunner, tmp_path: Path):
    src_dir = Path(__file__).parent.parent / "examples" / "minimal_project"
    dst = tmp_path / "project"
    dst.mkdir()
    shutil.copy(src_dir / "main.kicad_pcb", dst / "main.kicad_pcb")

    config = """\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: ""

probe_interface:
  type: test_pad
  side: top
  pad_diameter_mm: 1.5
  min_probe_spacing_mm: 2.54
  preferred_grid_mm: 2.54
  require_silkscreen_labels: false
  require_fiducials: false
  require_tooling_holes: false

nets_to_expose:
  - net: GND
    role: ground
    required: true
"""
    cfg_path = dst / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")

    result = runner.invoke(main, ["generate", str(cfg_path), "-d", str(dst)])
    assert result.exit_code == 2, result.output
    assert "Coverage:" in result.output


def test_route(runner: CliRunner, tmp_path: Path):
    src_dir = Path(__file__).parent.parent / "examples" / "minimal_project"
    pcb_path = tmp_path / "main.kicad_pcb"
    shutil.copy(src_dir / "main.kicad_pcb", pcb_path)

    ses = """(session "test"
  (base_design "test")
  (route
    (net "GND"
      (wire (path TOP 150 0 0 10000 0))
    )
  )
)"""
    ses_path = tmp_path / "test.ses"
    ses_path.write_text(ses, encoding="utf-8")

    result = runner.invoke(main, ["route", str(pcb_path), str(ses_path)])
    assert result.exit_code == 0, result.output
    assert "Routed PCB written to" in result.output
    assert (tmp_path / "main.routed.kicad_pcb").exists()


def test_validate_with_testpoints(runner: CliRunner, tmp_path: Path):
    pcb_text = """(kicad_pcb
  (version 20240108)
  (general (thickness 1.6))
  (paper "A4")
  (layers
    (0 "F.Cu" signal)
    (44 "Edge.Cuts" user))
  (net 0 "")
  (net 1 "SIG")
  (gr_rect (start 0 0) (end 50 50)
    (stroke (width 0.1) (type default))
    (fill none) (layer "Edge.Cuts") (uuid "e"))
  (footprint "TestPoint:TestPoint_Pad_D1.5mm"
    (layer "F.Cu")
    (uuid "tp-1")
    (at 10 10)
    (property "Reference" "TP1"
      (at 10 8 0) (layer "F.SilkS")
      (effects (font (size 1 1) (thickness 0.15))))
    (pad "1" smd circle
      (at 0 0)
      (size 1.5 1.5)
      (layers "F.Cu" "F.Mask")
      (net 1 "SIG")))
)"""
    pcb_path = tmp_path / "board.kicad_pcb"
    pcb_path.write_text(pcb_text, encoding="utf-8")

    result = runner.invoke(main, ["validate", str(pcb_path)])
    assert result.exit_code == 0, result.output
    assert "pass constraint checks" in result.output.lower()


def test_generate_exit_code_matrix(runner: CliRunner, tmp_path: Path, monkeypatch):
    for verdict, expected in (
        ("PASS", 0),
        ("PASS_WITH_REVIEW", 2),
        ("BLOCKED", 3),
    ):
        project = tmp_path / verdict.lower()
        project.mkdir()
        cfg_path = project / "config.yaml"
        cfg_path.write_text(_minimal_config(), encoding="utf-8")

        def fake_run(_cfg, project_dir, verdict=verdict):
            out_dir = Path(project_dir) / "output"
            out_dir.mkdir()
            ReadinessReport(run_id="APR-CLI", verdict=verdict).write_json(
                out_dir / "readiness_report.json",
            )
            coverage = CoverageReport(
                total_nets_requested=1,
                covered=1,
                entries=[
                    NetCoverage("GND", NetRole.GROUND, True, True),
                ],
            )
            return coverage, None

        monkeypatch.setattr("ai_probe_router.cli.run", fake_run)

        result = runner.invoke(main, ["generate", str(cfg_path), "-d", str(project)])

        assert result.exit_code == expected, result.output
        assert f"Readiness: {verdict}" in result.output


def test_generate_strict_blocks_process_warnings(runner: CliRunner, tmp_path: Path):
    src_dir = Path(__file__).parent.parent / "examples" / "minimal_project"
    dst = tmp_path / "project"
    dst.mkdir()
    shutil.copy(src_dir / "main.kicad_pcb", dst / "main.kicad_pcb")
    shutil.copy(src_dir / "main.kicad_sch", dst / "main.kicad_sch")

    cfg_path = dst / "config.yaml"
    cfg_path.write_text(_minimal_config(), encoding="utf-8")

    result = runner.invoke(main, ["generate", str(cfg_path), "-d", str(dst), "--strict"])

    assert result.exit_code == 3, result.output
    assert "Strict readiness:" in result.output
    assert "Readiness: BLOCKED" in result.output


def _minimal_config() -> str:
    return """\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

probe_interface:
  type: test_pad
  side: top
  pad_diameter_mm: 1.5
  min_probe_spacing_mm: 2.54
  preferred_grid_mm: 2.54
  require_silkscreen_labels: false
  require_fiducials: false
  require_tooling_holes: false

nets_to_expose:
  - net: GND
    role: ground
    required: true
"""
