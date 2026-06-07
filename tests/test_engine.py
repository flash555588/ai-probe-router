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


def test_engine_protection_circuits(tmp_path):
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
  - net: NRST
    role: reset
    required: false
  - net: GND
    role: ground
    required: true

protection:
  enabled: true
  debug:
    type: series_resistor
    value: "33"
    package: "0402"
  reset:
    type: series_resistor
    value: "100"
    package: "0402"
"""
    (tmp_path / "config.yaml").write_text(config_yaml)
    cfg = load_config(tmp_path / "config.yaml")
    assert cfg.protection.enabled
    assert cfg.protection.get_protection("debug") is not None
    assert cfg.protection.get_protection("reset") is not None
    assert cfg.protection.get_protection("ground") is None

    report, _ = run(cfg, tmp_path)
    assert report.covered >= 2

    out_pcb = (tmp_path / "output" / "main.kicad_pcb").read_text(encoding="utf-8")
    assert "PROBE_SWDIO" in out_pcb
    assert "PROBE_NRST" in out_pcb
    assert "PROBE_GND" not in out_pcb


def test_engine_writes_module_report_for_schema_v2(tmp_path):
    config_yaml = """\
schema_version: 2

project:
  eda_tool: kicad
  board_file: ""
  schematic_file: ""

functional_modules:
  - name: power_observation
    type: current_voltage_monitor
    required: true
    rails: [VDD_3V3]
    telemetry_bus: i2c
"""
    (tmp_path / "config.yaml").write_text(config_yaml, encoding="utf-8")
    cfg = load_config(tmp_path / "config.yaml")

    report, _ = run(cfg, tmp_path)

    assert report.total_nets_requested == 0
    module_report = tmp_path / "output" / "module_report.txt"
    assert module_report.exists()
    assert "power_observation" in module_report.read_text(encoding="utf-8")
    assert (tmp_path / "output" / "module_graph_report.txt").exists()
    assert (tmp_path / "output" / "module_compatibility_report.txt").exists()
    assert (tmp_path / "output" / "bus_report.txt").exists()
    assert (tmp_path / "output" / "power_report.txt").exists()
    assert (tmp_path / "output" / "routing_feasibility_report.txt").exists()
    assert (tmp_path / "output" / "module_placement_report.txt").exists()
    instantiation = tmp_path / "output" / "module_instantiation_report.txt"
    assert instantiation.exists()
    assert "SKIPPED (no_schematic)" in instantiation.read_text(encoding="utf-8")
    bom = tmp_path / "output" / "bom_report.csv"
    assert bom.exists()
    assert "module_id,module_name" in bom.read_text(encoding="utf-8")
