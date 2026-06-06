"""Integration test: full engine pipeline."""

import shutil
from pathlib import Path

from ai_probe_router.config import load_config
from ai_probe_router.engine import run


def test_engine_phase1(tmp_path):
    examples = Path(__file__).parent.parent / "examples"
    config_src = examples / "sample_config.yaml"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"
    if not all(p.exists() for p in [config_src, pcb_src, sch_src]):
        return

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")
    shutil.copy(config_src, tmp_path / "config.yaml")

    cfg = load_config(tmp_path / "config.yaml")
    report, pin_report = run(cfg, tmp_path)

    assert report.total_nets_requested == 9
    assert report.covered > 0
    assert report.coverage_pct > 0

    out_dir = tmp_path / "output"
    assert out_dir.exists()
    assert (out_dir / "main.kicad_pcb").exists()
    assert (out_dir / "main.kicad_sch").exists()
    assert (out_dir / "testpoint_report.txt").exists()


def test_engine_phase1_coverage_100(tmp_path):
    examples = Path(__file__).parent.parent / "examples"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"
    if not all(p.exists() for p in [pcb_src, sch_src]):
        return

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")

    config_yaml = """\
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

nets_to_expose:
  - net: SWDIO
    role: debug
    required: true
  - net: GND
    role: ground
    required: true
"""
    (tmp_path / "config.yaml").write_text(config_yaml)
    cfg = load_config(tmp_path / "config.yaml")
    report, _ = run(cfg, tmp_path)
    assert report.coverage_pct == 100.0
    assert report.covered == 2


def test_engine_constraint_validation(tmp_path):
    examples = Path(__file__).parent.parent / "examples"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"
    if not all(p.exists() for p in [pcb_src, sch_src]):
        return

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")

    config_yaml = """\
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

nets_to_expose:
  - net: SWDIO
    role: debug
    required: true

placement_rules:
  min_distance_from_board_edge_mm: 2.0
"""
    (tmp_path / "config.yaml").write_text(config_yaml)
    cfg = load_config(tmp_path / "config.yaml")
    report, _ = run(cfg, tmp_path)
    assert report.constraint_ok is not None
