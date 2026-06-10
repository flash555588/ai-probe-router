"""Integration test: IoT sensor node dev-board requirement end-to-end."""

import shutil
from pathlib import Path

from ai_probe_router.config import load_config
from ai_probe_router.engine import run


def _fix_dev_board_path(config_path: Path, dev_board_path: Path) -> None:
    text = config_path.read_text(encoding="utf-8")
    text = text.replace(
        "../ai_probe_router/libraries/dev_boards/stm32_nucleo_64.yaml",
        str(dev_board_path).replace("\\", "/"),
    )
    config_path.write_text(text, encoding="utf-8")

def test_iot_sensor_node_full_pipeline(tmp_path):
    repo_root = Path(__file__).parent.parent
    examples = repo_root / "examples"
    config_src = examples / "iot_sensor_node_config.yaml"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"
    dev_board = repo_root / "ai_probe_router" / "libraries" / "dev_boards" / "stm32_nucleo_64.yaml"

    assert config_src.exists(), f"Config missing: {config_src}"
    assert pcb_src.exists(), f"PCB missing: {pcb_src}"
    assert sch_src.exists(), f"Schematic missing: {sch_src}"
    assert dev_board.exists(), f"Dev board missing: {dev_board}"

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")
    shutil.copy(config_src, tmp_path / "config.yaml")
    _fix_dev_board_path(tmp_path / "config.yaml", dev_board)

    cfg = load_config(tmp_path / "config.yaml")

    # Schema v2 functional modules loaded
    assert cfg.schema_version == 2
    assert len(cfg.functional_modules) == 2
    assert cfg.functional_modules[0].name == "debug_access"
    assert cfg.functional_modules[1].name == "power_observation"

    # Protection enabled with specific rules
    assert cfg.protection.enabled
    assert cfg.protection.get_protection("debug") is not None
    assert cfg.protection.get_protection("reset") is not None
    assert cfg.protection.get_protection("power") is not None

    # Development board configured
    assert cfg.development_board is not None

    report, pin_report = run(cfg, tmp_path)

    # All 7 nets requested and covered
    assert report.total_nets_requested == 7
    assert report.covered == 7
    assert report.coverage_pct == 100.0

    # Output directory and files
    out_dir = tmp_path / "output"
    assert out_dir.exists()
    assert (out_dir / "main.kicad_pcb").exists()
    assert (out_dir / "main.kicad_sch").exists()
    assert (out_dir / "testpoint_report.txt").exists()

    # Schema v2 reports
    assert (out_dir / "module_report.txt").exists()
    assert (out_dir / "module_graph_report.txt").exists()
    assert (out_dir / "module_compatibility_report.txt").exists()
    assert (out_dir / "bus_report.txt").exists()
    assert (out_dir / "power_report.txt").exists()
    assert (out_dir / "routing_feasibility_report.txt").exists()
    assert (out_dir / "module_placement_report.txt").exists()
    assert (out_dir / "module_instantiation_report.txt").exists()
    assert (out_dir / "bom_report.csv").exists()

    # Module report contains our modules
    module_text = (out_dir / "module_report.txt").read_text(encoding="utf-8")
    assert "debug_access" in module_text
    assert "power_observation" in module_text

    # Power report mentions our voltage domain
    power_text = (out_dir / "power_report.txt").read_text(encoding="utf-8")
    assert "VDD_3V3" in power_text

    # Pin mapping report exists and contains mappings
    assert (out_dir / "pin_mapping_report.txt").exists()
    pin_text = (out_dir / "pin_mapping_report.txt").read_text(encoding="utf-8")
    assert "SWDIO" in pin_text
    assert "SWCLK" in pin_text

    # Protection circuits in generated PCB
    out_pcb = (out_dir / "main.kicad_pcb").read_text(encoding="utf-8")
    assert "PROBE_SWDIO" in out_pcb
    assert "PROBE_NRST" in out_pcb
    # UART_TX/UART_RX are communication nets; no protection is configured for
    # communication role, so they connect directly without PROBE_ prefix.
    assert "PROBE_UART_TX" not in out_pcb
    assert "PROBE_UART_RX" not in out_pcb
    # Ground does not get a probe prefix because no protection
    # Ground does not get a probe prefix because no protection
    assert "PROBE_GND" not in out_pcb
    # 3V3 has power protection (ferrite bead), so it gets PROBE_ prefix
    assert "PROBE_3V3" in out_pcb

    # Fiducials and tooling holes generated
    assert "FID" in out_pcb
    assert "TH" in out_pcb

    # Generated schematic has protection symbols
    out_sch = (out_dir / "main.kicad_sch").read_text(encoding="utf-8")
    assert "PROBE_SWDIO" in out_sch


def test_iot_sensor_node_config_validation(tmp_path):
    repo_root = Path(__file__).parent.parent
    examples = repo_root / "examples"
    config_src = examples / "iot_sensor_node_config.yaml"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"
    dev_board = repo_root / "ai_probe_router" / "libraries" / "dev_boards" / "stm32_nucleo_64.yaml"

    assert all(p.exists() for p in [config_src, pcb_src, sch_src, dev_board])

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")
    shutil.copy(config_src, tmp_path / "config.yaml")
    _fix_dev_board_path(tmp_path / "config.yaml", dev_board)

    cfg = load_config(tmp_path / "config.yaml")

    # Placement rules loaded
    assert cfg.constraints.placement.min_distance_from_board_edge_mm == 2.0
    assert cfg.constraints.placement.keep_probe_pads_on_grid is True

    # Routing rules loaded
    assert cfg.constraints.routing.default_trace_width_mm == 0.15
    assert cfg.constraints.routing.power_trace_width_mm == 0.5
    assert cfg.constraints.routing.min_clearance_mm == 0.15

    # Probe config
    assert cfg.probe.style.name == "TEST_PAD"
    assert cfg.probe.pad_diameter_mm == 1.27
    assert cfg.probe.min_spacing_mm == 2.54
    assert cfg.probe.require_fiducials is True
    assert cfg.probe.require_tooling_holes is True

    # Design goals
    assert "manufacturability" in cfg.design_goals.optimize_for
    assert "test_coverage" in cfg.design_goals.optimize_for
    assert cfg.design_goals.max_added_area_mm2 == 800


def test_iot_sensor_node_constraint_pass(tmp_path):
    repo_root = Path(__file__).parent.parent
    examples = repo_root / "examples"
    config_src = examples / "iot_sensor_node_config.yaml"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"
    dev_board = repo_root / "ai_probe_router" / "libraries" / "dev_boards" / "stm32_nucleo_64.yaml"

    assert all(p.exists() for p in [config_src, pcb_src, sch_src, dev_board])

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")
    shutil.copy(config_src, tmp_path / "config.yaml")
    _fix_dev_board_path(tmp_path / "config.yaml", dev_board)

    cfg = load_config(tmp_path / "config.yaml")
    report, _ = run(cfg, tmp_path)

    assert report.constraint_ok is True
    assert report.constraint_violations == 0
