"""Tests for CircuitSpec extraction and validation."""

from __future__ import annotations

from pathlib import Path

import yaml

from ai_probe_router.config import load_config
from ai_probe_router.models.circuit_spec import build_circuit_spec
from ai_probe_router.verification.circuit_spec_report import validate_circuit_spec


def test_audio_config_builds_valid_circuit_spec():
    repo_root = Path(__file__).parent.parent
    cfg = load_config(repo_root / "examples/audio_player_project/audio_player_config.yaml")

    spec = build_circuit_spec(cfg, schematic_net_names={"SWDIO", "USB_DP", "USB_DM"})
    report = validate_circuit_spec(spec)

    assert "VDD_3V3_D" in spec.rail_names
    assert "USB_DP" in spec.net_names
    assert not report.issues
    assert not report.errors


def test_circuit_spec_flags_interface_typo(tmp_path: Path):
    repo_root = Path(__file__).parent.parent
    raw = yaml.safe_load(
        (repo_root / "examples/audio_player_project/audio_player_config.yaml")
        .read_text(encoding="utf-8")
    )
    flash = next(m for m in raw["functional_modules"] if m["name"] == "flash_storage")
    flash["params"]["interface"] = "spi_qaud"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(raw), encoding="utf-8")

    cfg = load_config(config_path)
    report = validate_circuit_spec(build_circuit_spec(cfg))

    typo = next(issue for issue in report.errors if issue.code == "SPEC-UNKNOWN-PARAM-INTERFACE")
    assert typo.module_name == "flash_storage"
    assert "spi_quad" in typo.suggestion


def test_circuit_spec_flags_unknown_rail(tmp_path: Path):
    repo_root = Path(__file__).parent.parent
    raw = yaml.safe_load(
        (repo_root / "examples/audio_player_project/audio_player_config.yaml")
        .read_text(encoding="utf-8")
    )
    raw["functional_modules"][0]["rails"] = ["VDD_UNKNOWN"]
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(raw), encoding="utf-8")

    cfg = load_config(config_path)
    report = validate_circuit_spec(build_circuit_spec(cfg))

    assert any(issue.code == "SPEC-UNKNOWN-RAIL" for issue in report.errors)
