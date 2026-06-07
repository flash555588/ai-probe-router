"""End-to-end test for advanced IoT sensor node with 19 nets, diff pairs, impedance control."""

import shutil
from pathlib import Path

from ai_probe_router.config import load_config
from ai_probe_router.engine import run


def test_advanced_iot_full_coverage(tmp_path):
    repo_root = Path(__file__).parent.parent
    examples = repo_root / "examples"
    config_src = examples / "iot_sensor_node_advanced_config.yaml"
    project_src = examples / "iot_sensor_node_project"
    dev_board = repo_root / "libraries" / "dev_boards" / "stm32_nucleo_64.yaml"

    assert config_src.exists()
    assert (project_src / "main.kicad_pcb").exists()
    assert (project_src / "main.kicad_sch").exists()
    assert dev_board.exists()

    # Copy project to tmp_path
    for f in ["main.kicad_pcb", "main.kicad_sch"]:
        shutil.copy(project_src / f, tmp_path / f)
    shutil.copy(config_src, tmp_path / "config.yaml")

    mcu_profile_src = repo_root / "libraries" / "mcu_profiles" / "esp32_s3.yaml"
    if mcu_profile_src.exists():
        shutil.copy(mcu_profile_src, tmp_path / "esp32_s3.yaml")

    def _fix_paths(config_path: Path, dev_board_path: Path) -> None:
        text = config_path.read_text(encoding="utf-8")
        text = text.replace(
            "../libraries/dev_boards/stm32_nucleo_64.yaml",
            str(dev_board_path).replace("\\", "/"),
        )
        text = text.replace(
            "../libraries/mcu_profiles/esp32_s3.yaml",
            "esp32_s3.yaml",
        )
        config_path.write_text(text, encoding="utf-8")

    _fix_paths(tmp_path / "config.yaml", dev_board)

    cfg = load_config(tmp_path / "config.yaml")

    # Schema v2 with 5 functional modules
    assert cfg.schema_version == 2
    assert len(cfg.functional_modules) == 5
    assert cfg.functional_modules[0].name == "debug_access"
    assert cfg.functional_modules[2].name == "analog_frontend"

    # Impedance control parsed
    assert cfg.impedance_control.has_rules()
    usb_rule = cfg.impedance_control.get_rule("usb")
    assert usb_rule is not None
    assert usb_rule.target_impedance_ohm == 90.0
    can_rule = cfg.impedance_control.get_rule("can")
    assert can_rule is not None
    assert can_rule.target_impedance_ohm == 120.0

    # Thermal analysis parsed
    assert cfg.thermal_analysis.enabled is True
    assert cfg.thermal_analysis.max_junction_temp_c == 125.0

    # Differential pairs configured
    pair_reqs = [r for r in cfg.nets_to_expose if r.pair_net_name]
    assert len(pair_reqs) == 4  # CAN_H, CAN_L, USB_DP, USB_DM

    report, pin_report = run(cfg, tmp_path)

    # 100% coverage (19/19)
    assert report.total_nets_requested == 19
    assert report.covered == 19
    assert report.coverage_pct == 100.0

    # Constraint pass
    assert report.constraint_ok is True

    # Output files
    out_dir = tmp_path / "output"
    assert out_dir.exists()
    assert (out_dir / "main.kicad_pcb").exists()
    assert (out_dir / "main.kicad_sch").exists()

    # Schema v2 reports all present
    assert (out_dir / "module_report.txt").exists()
    assert (out_dir / "module_graph_report.txt").exists()
    assert (out_dir / "module_compatibility_report.txt").exists()
    assert (out_dir / "bus_report.txt").exists()
    assert (out_dir / "power_report.txt").exists()
    assert (out_dir / "routing_feasibility_report.txt").exists()
    assert (out_dir / "module_placement_report.txt").exists()
    assert (out_dir / "module_instantiation_report.txt").exists()
    assert (out_dir / "bom_report.csv").exists()
    assert (out_dir / "pin_mapping_report.txt").exists()
    assert (out_dir / "manufacturing_report.txt").exists()

    # Pin mapping report: diff pair assigned adjacently
    pin_text = (out_dir / "pin_mapping_report.txt").read_text(encoding="utf-8")
    assert "CAN_H" in pin_text
    assert "CAN_L" in pin_text
    assert "D3_PB3" in pin_text
    assert "D4_PB5" in pin_text

    # Module report contains all modules
    module_text = (out_dir / "module_report.txt").read_text(encoding="utf-8")
    assert "debug_access" in module_text
    assert "analog_frontend" in module_text
    assert "field_bus" in module_text
    assert "io_expansion" in module_text

    # Power report mentions voltage domains
    power_text = (out_dir / "power_report.txt").read_text(encoding="utf-8")
    assert "VDD_3V3" in power_text

    # BOM report is non-empty CSV
    bom_text = (out_dir / "bom_report.csv").read_text(encoding="utf-8")
    assert len(bom_text.splitlines()) > 1

    # Generated PCB contains testpoints for all nets
    out_pcb = (out_dir / "main.kicad_pcb").read_text(encoding="utf-8")
    assert "TP1" in out_pcb
    assert "FID" in out_pcb
    assert "TH" in out_pcb

    # Protection circuits present
    assert "PROBE_SWDIO" in out_pcb
    assert "PROBE_NRST" in out_pcb

    # High-speed nets get review flag
    assert any(e.review_required for e in report.entries if e.net_name == "USB_DP")
    assert any(e.review_required for e in report.entries if e.net_name == "USB_DM")
    assert any(e.review_required for e in report.entries if e.net_name == "ADC_IN0")


def test_advanced_iot_diff_pair_pin_mapper():
    from ai_probe_router.solvers.pin_mapper import solve_mapping
    from ai_probe_router.models.probe import ProbeRequirement
    from ai_probe_router.models.dev_board import DevelopmentBoard, DevBoardPin

    board = DevelopmentBoard(
        name="test_board",
        pins=[
            DevBoardPin(name="P1", capabilities=["GPIO", "CAN"], current_rating_ma=25),
            DevBoardPin(name="P2", capabilities=["GPIO", "CAN"], current_rating_ma=25),
            DevBoardPin(name="P3", capabilities=["GPIO"], current_rating_ma=25),
        ],
        rows=2,
        pins_per_row=2,
        pitch_mm=2.54,
    )

    reqs = [
        ProbeRequirement(net_name="CAN_H", role="communication", pair_net_name="CAN_L", preferred_devboard_pins=["P1"]),
        ProbeRequirement(net_name="CAN_L", role="communication", pair_net_name="CAN_H", preferred_devboard_pins=["P2"]),
    ]

    result = solve_mapping(reqs, board)
    assigned_nets = {a.net_name for a in result.assignments}
    assert "CAN_H" in assigned_nets
    assert "CAN_L" in assigned_nets

    # Adjacent pins for 2x2 header: P1(index0) and P2(index1) are adjacent
    can_h_pin = next(a.pin_name for a in result.assignments if a.net_name == "CAN_H")
    can_l_pin = next(a.pin_name for a in result.assignments if a.net_name == "CAN_L")
    assert {can_h_pin, can_l_pin} == {"P1", "P2"}


def test_impedance_control_parsed(tmp_path):
    config_text = """\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

probe_interface:
  type: test_pad

nets_to_expose:
  - net: TEST
    role: digital

impedance_control:
  usb:
    target_impedance_ohm: 90
    diff_pair_width_mm: 0.12
    diff_pair_gap_mm: 0.18
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config_text, encoding="utf-8")
    cfg = load_config(cfg_path)
    assert cfg.impedance_control.has_rules()
    rule = cfg.impedance_control.get_rule("usb")
    assert rule.target_impedance_ohm == 90.0
    assert rule.diff_pair_width_mm == 0.12
    assert rule.diff_pair_gap_mm == 0.18


def test_thermal_analysis_parsed(tmp_path):
    config_text = """\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

probe_interface:
  type: test_pad

nets_to_expose:
  - net: TEST
    role: digital

thermal_analysis:
  enabled: true
  max_junction_temp_c: 150
  ambient_temp_c: 40
  output_format: json
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config_text, encoding="utf-8")
    cfg = load_config(cfg_path)
    assert cfg.thermal_analysis.enabled is True
    assert cfg.thermal_analysis.max_junction_temp_c == 150.0
    assert cfg.thermal_analysis.ambient_temp_c == 40.0
    assert cfg.thermal_analysis.output_format == "json"
