"""Tests for deterministic pre-KiCad ERC checks."""

from __future__ import annotations

from pathlib import Path

import yaml

from ai_probe_router.config import load_config
from ai_probe_router.models.circuit_spec import build_circuit_spec
from ai_probe_router.verification.erc_report import run_preflight_erc


def test_audio_config_preflight_erc_has_no_errors():
    repo_root = Path(__file__).parent.parent
    cfg = load_config(repo_root / "examples/audio_player_project/audio_player_config.yaml")

    report = run_preflight_erc(build_circuit_spec(cfg))

    assert not report.errors
    assert any(f.check_id == "ERC-004" for f in report.warnings)


def test_preflight_erc_flags_missing_required_rail(tmp_path: Path):
    repo_root = Path(__file__).parent.parent
    raw = yaml.safe_load(
        (repo_root / "examples/audio_player_project/audio_player_config.yaml")
        .read_text(encoding="utf-8")
    )
    raw["functional_modules"][0]["rails"] = ["VDD_UNKNOWN"]
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(raw), encoding="utf-8")

    cfg = load_config(config_path)
    report = run_preflight_erc(build_circuit_spec(cfg))

    assert any(f.check_id == "ERC-001" and f.severity == "error" for f in report.findings)


def test_preflight_erc_usb_cc_warning_clears_when_documented(tmp_path: Path):
    repo_root = Path(__file__).parent.parent
    raw = yaml.safe_load(
        (repo_root / "examples/audio_player_project/audio_player_config.yaml")
        .read_text(encoding="utf-8")
    )
    usb = next(m for m in raw["functional_modules"] if m["name"] == "usb_c_port")
    usb["params"]["cc_role"] = "device_rd_5k1"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(raw), encoding="utf-8")

    cfg = load_config(config_path)
    report = run_preflight_erc(build_circuit_spec(cfg))

    assert not [
        f
        for f in report.findings
        if f.check_id == "ERC-004" and "role/CC pull" in f.message
    ]
