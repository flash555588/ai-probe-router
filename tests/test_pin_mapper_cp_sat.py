"""Tests for optional CP-SAT pin mapping."""

from __future__ import annotations

import pytest

from ai_probe_router.config import ProjectConfig, load_config
from ai_probe_router.engine import _select_pin_mapping
from ai_probe_router.models.dev_board import DevBoardPin, DevelopmentBoard
from ai_probe_router.models.probe import ProbeRequirement
from ai_probe_router.solvers.pin_mapper_cp_sat import map_pins_cp_sat


def test_default_pin_mapper_mode_is_greedy(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(_config(""), encoding="utf-8")

    cfg = load_config(cfg_path)

    assert cfg.pin_mapper.mode == "greedy"
    assert cfg.pin_mapper.fallback_to_greedy


def test_cp_sat_and_compare_modes_parse(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(_config("""\
pin_mapper:
  mode: cp_sat
  fallback_to_greedy: false
  require_ortools: true
  objective_weights:
    preferred_pin: 120
"""), encoding="utf-8")
    cfg = load_config(cfg_path)
    assert cfg.pin_mapper.mode == "cp_sat"
    assert not cfg.pin_mapper.fallback_to_greedy
    assert cfg.pin_mapper.require_ortools
    assert cfg.pin_mapper.objective_weights.preferred_pin == 120

    cfg_path.write_text(_config("""\
pin_mapper:
  mode: compare
  selected_output: cp_sat
"""), encoding="utf-8")
    cfg = load_config(cfg_path)
    assert cfg.pin_mapper.mode == "compare"
    assert cfg.pin_mapper.selected_output == "cp_sat"


def test_invalid_pin_mapper_mode_fails_config_validation(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(_config("""\
pin_mapper:
  mode: magic
"""), encoding="utf-8")

    with pytest.raises(ValueError, match="pin_mapper.mode"):
        load_config(cfg_path)


def test_cp_sat_basic_gpio_mapping():
    result = map_pins_cp_sat(
        [ProbeRequirement(net_name="GPIO_A", role="gpio", required=True)],
        _board([DevBoardPin(name="PA0", capabilities=["GPIO"])]),
    )

    assert result.ok
    assert result.assignments[0].pin_name == "PA0"
    assert result.solver == "cp_sat"


def test_cp_sat_rejects_capability_mismatch():
    result = map_pins_cp_sat(
        [ProbeRequirement(net_name="USB_DP", role="high_speed", required=True)],
        _board([DevBoardPin(name="PA0", capabilities=["GPIO"])]),
    )

    assert not result.ok
    assert "CP_SAT_NO_FEASIBLE_MAPPING" in result.errors[0]


def test_cp_sat_rejects_duplicate_pin_assignment():
    result = map_pins_cp_sat(
        [
            ProbeRequirement(net_name="GPIO_A", role="gpio", required=True),
            ProbeRequirement(net_name="GPIO_B", role="gpio", required=True),
        ],
        _board([DevBoardPin(name="PA0", capabilities=["GPIO"])]),
    )

    assert not result.ok
    assert "CP_SAT_NO_FEASIBLE_MAPPING" in result.errors[0]


def test_cp_sat_honors_required_preferred_pin():
    result = map_pins_cp_sat(
        [
            ProbeRequirement(
                net_name="GPIO_A",
                role="gpio",
                required=True,
                preferred_devboard_pins=["PA1"],
            ),
        ],
        _board([
            DevBoardPin(name="PA0", capabilities=["GPIO"]),
            DevBoardPin(name="PA1", capabilities=["GPIO"]),
        ]),
    )

    assert result.ok
    assert result.assignments[0].pin_name == "PA1"


def test_cp_sat_falls_back_when_ortools_missing(monkeypatch):
    cfg = ProjectConfig()
    cfg.pin_mapper.mode = "cp_sat"
    cfg.pin_mapper.fallback_to_greedy = True
    cfg.nets_to_expose = [ProbeRequirement(net_name="GPIO_A", role="gpio", required=True)]
    monkeypatch.setattr("ai_probe_router.engine.ortools_available", lambda: False)

    result, compare = _select_pin_mapping(cfg, _board([DevBoardPin("PA0", ["GPIO"])]))

    assert compare is None
    assert result.ok
    assert result.solver == "greedy"
    assert "ORTOOLS_MISSING_FALLBACK_TO_GREEDY" in result.warnings


def test_cp_sat_required_blocks_when_ortools_missing(monkeypatch):
    cfg = ProjectConfig()
    cfg.pin_mapper.mode = "cp_sat"
    cfg.pin_mapper.fallback_to_greedy = False
    cfg.nets_to_expose = [ProbeRequirement(net_name="GPIO_A", role="gpio", required=True)]
    monkeypatch.setattr("ai_probe_router.engine.ortools_available", lambda: False)

    result, compare = _select_pin_mapping(cfg, _board([DevBoardPin("PA0", ["GPIO"])]))

    assert compare is None
    assert not result.ok
    assert "CP_SAT_REQUIRED_BUT_ORTOOLS_MISSING" in result.errors


def test_greedy_mode_does_not_require_ortools(monkeypatch):
    cfg = ProjectConfig()
    cfg.pin_mapper.mode = "greedy"
    cfg.nets_to_expose = [ProbeRequirement(net_name="GPIO_A", role="gpio", required=True)]
    monkeypatch.setattr("ai_probe_router.engine.ortools_available", lambda: False)

    result, _compare = _select_pin_mapping(cfg, _board([DevBoardPin("PA0", ["GPIO"])]))

    assert result.ok
    assert not result.warnings


def _board(pins: list[DevBoardPin]) -> DevelopmentBoard:
    return DevelopmentBoard(
        name="dev",
        connector_type="header",
        pins_per_row=max(len(pins), 1),
        rows=1,
        pins=pins,
    )


def _config(extra: str) -> str:
    return f"""\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

nets_to_expose:
  - net: GPIO_A
    role: gpio

{extra}
"""
