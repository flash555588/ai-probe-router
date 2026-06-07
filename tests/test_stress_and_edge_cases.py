"""Stress and edge-case tests for the probe router engine."""

import shutil
from pathlib import Path

from ai_probe_router.config import load_config
from ai_probe_router.engine import run
from ai_probe_router.models.protection import ProtectionType, protection_type_from_string


def test_stress_many_nets(tmp_path):
    """Stress test: 50 nets on a minimal board."""
    repo_root = Path(__file__).parent.parent
    examples = repo_root / "examples"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")

    nets_yaml = "\n".join(
        f'  - net: NET_{i:02d}\n    role: digital\n    required: true'
        for i in range(50)
    )
    config_text = f"""\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

probe_interface:
  type: test_pad
  pad_diameter_mm: 0.8
  min_probe_spacing_mm: 1.27

nets_to_expose:
{nets_yaml}

placement_rules:
  min_distance_from_board_edge_mm: 1.0
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config_text, encoding="utf-8")

    cfg = load_config(cfg_path)
    assert len(cfg.nets_to_expose) == 50

    report, _ = run(cfg, tmp_path)

    # All existing nets on the board should be covered; extra nets will be missing
    # but engine should not crash
    assert report.total_nets_requested == 50
    assert report.covered <= 50
    assert report.coverage_pct >= 0


def test_edge_missing_net_no_crash(tmp_path):
    """Edge case: config asks for a net that does not exist on the board."""
    repo_root = Path(__file__).parent.parent
    examples = repo_root / "examples"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")

    config_text = """\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

probe_interface:
  type: test_pad

nets_to_expose:
  - net: NONEXISTENT_NET
    role: digital
    required: false
  - net: SWDIO
    role: debug
    required: true
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config_text, encoding="utf-8")

    cfg = load_config(cfg_path)
    report, _ = run(cfg, tmp_path)

    assert report.total_nets_requested == 2
    assert report.covered == 1  # SWDIO only
    assert report.missing == 1
    assert report.coverage_pct == 50.0


def test_edge_conflicting_constraints(tmp_path):
    """Edge case: very tight constraints that may cause placement failures."""
    repo_root = Path(__file__).parent.parent
    examples = repo_root / "examples"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")

    config_text = """\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

probe_interface:
  type: test_pad
  pad_diameter_mm: 5.0
  min_probe_spacing_mm: 10.0

nets_to_expose:
  - net: SWDIO
    role: debug
    required: true
  - net: SWCLK
    role: debug
    required: true

placement_rules:
  min_distance_from_board_edge_mm: 10.0
  keep_probe_pads_on_grid: true
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config_text, encoding="utf-8")

    cfg = load_config(cfg_path)
    report, _ = run(cfg, tmp_path)

    # With 40x40 mm board, 10 mm edge clearance, and 5 mm pads with 10 mm spacing,
    # placement is extremely constrained. Engine should still run without crash.
    assert report.total_nets_requested == 2
    # Some may fail to place, but engine must not crash
    assert report.covered <= 2


def test_protection_all_types(tmp_path):
    """Verify all protection types can be parsed from config strings."""
    types_to_test = [
        ("series_resistor", ProtectionType.SERIES_RESISTOR),
        ("ferrite_bead", ProtectionType.FERRITE_BEAD),
        ("esd_array", ProtectionType.ESD_ARRAY),
        ("tvs_diode", ProtectionType.TVS_DIODE),
        ("level_shifter", ProtectionType.LEVEL_SHIFTER),
        ("current_limiter", ProtectionType.CURRENT_LIMITER),
        ("efuse", ProtectionType.EFUSE),
        ("jumper", ProtectionType.JUMPER),
    ]
    for string, expected in types_to_test:
        result = protection_type_from_string(string)
        assert result == expected, f"{string} -> {result} != {expected}"


def test_edge_duplicate_probe_count(tmp_path):
    """Edge case: multiple duplicate probes for a single net."""
    repo_root = Path(__file__).parent.parent
    examples = repo_root / "examples"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")

    config_text = """\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

probe_interface:
  type: test_pad
  pad_diameter_mm: 0.8
  min_probe_spacing_mm: 1.5

nets_to_expose:
  - net: GND
    role: ground
    required: true
    duplicate_probe_count: 8
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config_text, encoding="utf-8")

    cfg = load_config(cfg_path)
    report, _ = run(cfg, tmp_path)

    assert report.total_nets_requested == 1
    assert report.covered == 1
    # 8 duplicate probes should all be placed
    out_pcb = (tmp_path / "output" / "main.kicad_pcb").read_text(encoding="utf-8")
    tp_count = out_pcb.count('"TP')
    assert tp_count >= 8
