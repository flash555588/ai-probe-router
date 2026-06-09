"""Tests for data models and net classifier."""

import pytest

from ai_probe_router.ai.net_classifier import classify_net
from ai_probe_router.config import ConfigValidationError, load_config
from ai_probe_router.models.board import Board, Footprint, Pad
from ai_probe_router.models.net import NetRole
from ai_probe_router.models.protection import ProtectionType


def test_classify_power():
    assert classify_net("3V3") == NetRole.POWER
    assert classify_net("5V") == NetRole.POWER
    assert classify_net("VCC") == NetRole.POWER
    assert classify_net("VBUS") == NetRole.POWER


def test_classify_ground():
    assert classify_net("GND") == NetRole.GROUND
    assert classify_net("AGND") == NetRole.GROUND


def test_classify_debug():
    assert classify_net("SWDIO") == NetRole.DEBUG
    assert classify_net("SWCLK") == NetRole.DEBUG


def test_classify_communication():
    assert classify_net("UART_TX") == NetRole.COMMUNICATION
    assert classify_net("I2C_SCL") == NetRole.COMMUNICATION
    assert classify_net("SPI_MOSI") == NetRole.COMMUNICATION


def test_classify_reset():
    assert classify_net("NRST") == NetRole.RESET
    assert classify_net("RESET") == NetRole.RESET


def test_classify_high_speed():
    assert classify_net("USB_DP") == NetRole.HIGH_SPEED


def test_classify_unknown():
    assert classify_net("MY_CUSTOM_NET") == NetRole.UNKNOWN


def test_board_find_pads_by_net():
    pad1 = Pad(number="1", net_name="GND", net_id=1)
    pad2 = Pad(number="2", net_name="3V3", net_id=2)
    fp = Footprint(ref="U1", pads=[pad1, pad2])
    board = Board(footprints=[fp], nets={"GND": 1, "3V3": 2})
    found = board.find_pads_by_net("GND")
    assert len(found) == 1
    assert found[0][1].net_name == "GND"


def test_board_next_net_id():
    board = Board(nets={"GND": 1, "3V3": 2, "SWDIO": 5})
    assert board.next_net_id() == 6


def test_load_sample_config(tmp_path):
    import shutil
    from pathlib import Path
    src = Path(__file__).parent.parent / "examples" / "sample_config.yaml"
    dst = tmp_path / "config.yaml"
    shutil.copy(src, dst)
    cfg = load_config(dst)
    assert cfg.eda_tool == "kicad"
    assert len(cfg.nets_to_expose) == 9
    assert cfg.nets_to_expose[0].net_name == "SWDIO"
    assert cfg.probe.pad_diameter_mm == 1.5
    assert cfg.protection.get_protection("debug") is None


def test_load_config_missing_dev_board_raises(tmp_path):
    config = """\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

probe_interface:
  type: test_pad

nets_to_expose:
  - net: SWDIO
    role: debug

development_board:
  pin_database: nonexistent.yaml
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")
    try:
        load_config(cfg_path)
    except ValueError as exc:
        assert "nonexistent.yaml" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing dev board database")


def test_load_config_declares_dev_board_pin_database_field():
    from pathlib import Path

    cfg = load_config(Path(__file__).parent.parent / "examples" / "full_config.yaml")

    assert cfg.dev_board_pin_db == "../libraries/dev_boards/stm32_nucleo_64.yaml"


def test_load_config_empty_nets_raises(tmp_path):
    config = """\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

probe_interface:
  type: test_pad

nets_to_expose: []
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")
    try:
        load_config(cfg_path)
    except ValueError as exc:
        assert "nets_to_expose" in str(exc)
    else:
        raise AssertionError("Expected ValueError for empty nets_to_expose")


def test_load_config_rejects_malformed_top_level_section(tmp_path):
    config = """\
project:
  eda_tool: kicad
nets_to_expose:
  net: SWDIO
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")

    with pytest.raises(ConfigValidationError, match="nets_to_expose must be a YAML list"):
        load_config(cfg_path)


def test_load_config_rejects_missing_net_name_with_field_path(tmp_path):
    config = """\
project:
  eda_tool: kicad
nets_to_expose:
  - role: debug
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")

    with pytest.raises(ConfigValidationError, match=r"nets_to_expose\[0\]\.net is required"):
        load_config(cfg_path)


def test_load_config_rejects_invalid_numeric_constraints_with_field_path(tmp_path):
    config = """\
project:
  eda_tool: kicad
nets_to_expose:
  - net: SWDIO
    role: debug
    duplicate_probe_count: 0
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")

    with pytest.raises(
        ConfigValidationError,
        match=r"nets_to_expose\[0\]\.duplicate_probe_count must be >= 1",
    ):
        load_config(cfg_path)


def test_load_config_rejects_malformed_functional_module_with_field_path(tmp_path):
    config = """\
schema_version: 2
project:
  eda_tool: kicad
functional_modules:
  - name: debug_access
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")

    with pytest.raises(ConfigValidationError, match=r"functional_modules\[0\]\.type is required"):
        load_config(cfg_path)


def test_load_config_rejects_malformed_process_waivers_with_field_path(tmp_path):
    config = """\
project:
  eda_tool: kicad
nets_to_expose:
  - net: SWDIO
process_controls:
  waivers:
    issue_id: electrical_review_required
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")

    with pytest.raises(
        ConfigValidationError,
        match=r"process_controls\.waivers must be a YAML list",
    ):
        load_config(cfg_path)


def test_load_config_rejects_unsupported_schema_version(tmp_path):
    config = """\
schema_version: 99
project:
  eda_tool: kicad
nets_to_expose:
  - net: SWDIO
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")

    with pytest.raises(ConfigValidationError, match="Unsupported schema_version 99"):
        load_config(cfg_path)


def test_load_config_rejects_unknown_top_level_key(tmp_path):
    config = """\
project:
  eda_tool: kicad
nets_to_expose:
  - net: SWDIO
mystery_section: {}
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")

    with pytest.raises(
        ConfigValidationError,
        match=r"Unsupported config key: config\.mystery_section",
    ):
        load_config(cfg_path)


def test_load_config_rejects_unknown_project_key(tmp_path):
    config = """\
project:
  eda_tool: kicad
  boarad_file: main.kicad_pcb
nets_to_expose:
  - net: SWDIO
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")

    with pytest.raises(
        ConfigValidationError,
        match=r"Unsupported config key: project\.boarad_file",
    ):
        load_config(cfg_path)


def test_load_config_rejects_unknown_net_key(tmp_path):
    config = """\
project:
  eda_tool: kicad
nets_to_expose:
  - net: USB_DP
    pairwith: USB_DM
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")

    with pytest.raises(
        ConfigValidationError,
        match=r"Unsupported config key: nets_to_expose\[0\]\.pairwith",
    ):
        load_config(cfg_path)


def test_load_config_rejects_unknown_process_control_key(tmp_path):
    config = """\
project:
  eda_tool: kicad
nets_to_expose:
  - net: SWDIO
process_controls:
  strict_signof: true
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")

    with pytest.raises(
        ConfigValidationError,
        match=r"Unsupported config key: process_controls\.strict_signof",
    ):
        load_config(cfg_path)


def test_load_schema_v2_functional_modules_without_nets(tmp_path):
    config = """\
schema_version: 2

project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

design_goals:
  optimize_for: [manufacturability, low_bom_cost]
  max_added_area_mm2: 1200
  preferred_side: top
  human_review_required_for: [high_speed, rf]

hardware_platform:
  target_voltage_domains:
    - name: VDD_3V3
      voltage: 3.3
      max_current_ma: 800

functional_modules:
  - name: debug_access
    type: debug_swd
    required: true
    target_nets: [SWDIO, SWCLK, NRST, GND, 3V3]
    allowed_implementations: [protected_pogo]
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")

    cfg = load_config(cfg_path)

    assert cfg.schema_version == 2
    assert cfg.nets_to_expose == []
    assert cfg.functional_modules[0].name == "debug_access"
    assert cfg.functional_modules[0].allowed_implementations == ["protected_pogo"]
    assert cfg.hardware_platform.target_voltage_domains[0].voltage == 3.3
    assert cfg.design_goals.optimize_for == ["manufacturability", "low_bom_cost"]


def test_load_schema_v2_module_graph_fields(tmp_path):
    config = """\
schema_version: 2

project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

functional_modules:
  - name: analog_probe
    type: analog_measurement
    depends_on: [debug_access]
    budget_area_mm2: 250
    preferred_region: top
    version: "1.2"
    ai_hints:
      - type: sensitive_route
        target: analog_probe
      - type: unsupported_magic

routing_strategy:
  coarse_grid_mm: 4
  max_corridor_layers: 2
  congestion_weight: 12
  via_weight: 6
  length_weight: 1.5
  sensitive_net_spacing_mm: 7
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")

    cfg = load_config(cfg_path)
    module = cfg.functional_modules[0]

    assert module.depends_on == ["debug_access"]
    assert module.budget_area_mm2 == 250
    assert module.preferred_region == "top"
    assert module.version == "1.2"
    assert module.ai_hints[0].supported
    assert not module.ai_hints[1].supported
    assert cfg.routing_strategy.coarse_grid_mm == 4
    assert cfg.routing_strategy.sensitive_net_spacing_mm == 7


def test_load_schema_v2_module_params_and_constraints_are_explicit(tmp_path):
    config = """\
schema_version: 2

project:
  eda_tool: kicad

functional_modules:
  - name: flash_storage
    type: memory
    params:
      interface: spi_quad
    constraints:
      max_freq_mhz: 80
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")

    cfg = load_config(cfg_path)
    module = cfg.functional_modules[0]

    assert module.params["interface"] == "spi_quad"
    assert module.params["constraints"] == {"max_freq_mhz": 80}
    assert "params" not in module.params


def test_load_process_controls_and_waivers(tmp_path):
    config = """\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

nets_to_expose:
  - net: SWDIO
    role: debug

process_controls:
  strict_signoff: true
  require_autorouter_feedback: true
  require_manufacturing_exports: true
  scalability_module_warning_threshold: 2
  scalability_net_warning_threshold: 4
  waivers:
    - id: WV-1
      source: electrical_signoff
      issue_id: electrical_review_required
      owner: reviewer
      reason: external checklist complete
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")

    cfg = load_config(cfg_path)

    assert cfg.process_controls.strict_signoff
    assert cfg.process_controls.require_autorouter_feedback
    assert cfg.process_controls.require_manufacturing_exports
    assert cfg.process_controls.scalability_module_warning_threshold == 2
    assert cfg.process_controls.scalability_net_warning_threshold == 4
    assert cfg.process_controls.waivers[0].waiver_id == "WV-1"
    assert cfg.process_controls.waivers[0].complete


def test_load_process_control_params_are_explicit(tmp_path):
    config = """\
project:
  eda_tool: kicad
nets_to_expose:
  - net: SWDIO
process_controls:
  params:
    release_track: prototype
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")

    cfg = load_config(cfg_path)

    assert cfg.process_controls.params == {"release_track": "prototype"}


def test_load_module_footprint_preview_enabled_alias(tmp_path):
    config = """\
project:
  eda_tool: kicad
nets_to_expose:
  - net: SWDIO
module_footprint_preview:
  enabled: true
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")

    cfg = load_config(cfg_path)

    assert cfg.module_footprint_preview.enable


def test_load_audio_player_config_with_strict_schema():
    from pathlib import Path

    cfg = load_config(
        Path(__file__).parent.parent
        / "examples"
        / "audio_player_project"
        / "audio_player_config.yaml"
    )

    flash = next(module for module in cfg.functional_modules if module.name == "flash_storage")
    assert flash.params["interface"] == "spi_quad"
    assert cfg.module_footprint_preview.enable


def test_load_config_expanded_protection_type(tmp_path):
    config = """\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

probe_interface:
  type: test_pad

nets_to_expose:
  - net: SWDIO
    role: debug

protection:
  enabled: true
  debug:
    type: esd_array
    value: "low_cap"
"""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(config, encoding="utf-8")

    cfg = load_config(cfg_path)
    protection = cfg.protection.get_protection("debug")

    assert protection is not None
    assert protection.protection_type == ProtectionType.ESD_ARRAY
    assert protection.ref_prefix == "D"
