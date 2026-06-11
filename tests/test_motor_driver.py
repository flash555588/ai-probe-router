"""Integration test for the motor-driver example project."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from ai_probe_router.cli import main
from ai_probe_router.config import load_config
from ai_probe_router.engine import run

REPO_ROOT = Path(__file__).parent.parent
MOTOR_DIR = REPO_ROOT / "examples" / "motor_driver_project"
MOTOR_CFG = REPO_ROOT / "examples" / "motor_driver_config.yaml"
DB_SRC = (
    REPO_ROOT
    / "libraries"
    / "dev_boards"
    / "stm32_nucleo_64.yaml"
)


def _prepare_project(dst: Path) -> Path:
    """Copy motor-driver example files into *dst* and return config path."""
    dst.mkdir()
    shutil.copy(MOTOR_DIR / "main.kicad_pcb", dst / "main.kicad_pcb")
    shutil.copy(MOTOR_DIR / "main.kicad_sch", dst / "main.kicad_sch")
    shutil.copy(MOTOR_DIR / "main.kicad_pro", dst / "main.kicad_pro")
    # Dev board database must live next to config because config uses a
    # relative path.
    db_src = REPO_ROOT / "libraries" / "dev_boards" / "stm32_nucleo_64.yaml"
    db_dst = dst / "stm32_nucleo_64.yaml"
    shutil.copy(db_src, db_dst)
    cfg_text = MOTOR_CFG.read_text(encoding="utf-8")
    cfg_text = cfg_text.replace(
        "../libraries/dev_boards/stm32_nucleo_64.yaml",
        "stm32_nucleo_64.yaml",
    )
    cfg_path = dst / "config.yaml"
    cfg_path.write_text(cfg_text, encoding="utf-8")
    return cfg_path


@pytest.fixture(scope="module")
def motor_output(tmp_path_factory):
    """Run the motor-driver example once and cache the output directory."""
    tmp = tmp_path_factory.mktemp("motor_driver")
    dst = tmp / "project"
    cfg_path = _prepare_project(dst)
    cfg = load_config(cfg_path)
    coverage, pin_report = run(cfg, dst)
    return dst / "output", coverage, pin_report


def test_motor_driver_config_loads():
    cfg = load_config(MOTOR_CFG)
    assert cfg.eda_tool == "kicad"
    assert len(cfg.nets_to_expose) == 26
    assert cfg.probe.style.name == "TEST_PAD"


def test_motor_driver_coverage(motor_output):
    out_dir, coverage, _pin_report = motor_output
    # All 26 nets are covered (VM now gets a testpoint too).
    assert coverage.covered == 26
    assert coverage.total_nets_requested == 26


def test_motor_driver_output_artifacts(motor_output):
    out_dir, _coverage, _pin_report = motor_output
    required = [
        "main.kicad_pcb",
        "main.kicad_sch",
        "testpoint_report.txt",
        "readiness_report.txt",
        "decision_manifest.json",
        "pin_mapping_report.txt",
        "thermal_simulation.csv",
    ]
    for name in required:
        assert (out_dir / name).exists(), f"missing artifact: {name}"


def test_motor_driver_readiness_status(motor_output):
    _out_dir, coverage, _pin_report = motor_output
    # Expanded example has DRC footprint-library warnings (KiCad fallback),
    # so readiness is BLOCKED, but coverage is still 100%.
    assert coverage.readiness_verdict == "BLOCKED"


def test_motor_driver_native_validation_status(motor_output):
    _out_dir, coverage, _pin_report = motor_output
    # DRC reports warnings due to missing footprint libraries in the example;
    # ERC passes. Coverage and pin mapping still work.
    assert coverage.drc_ok is False
    assert coverage.erc_ok is True


def test_motor_driver_cli_end_to_end(tmp_path: Path):
    dst = tmp_path / "project"
    cfg_path = _prepare_project(dst)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["generate", str(cfg_path), "-d", str(dst)],
    )
    # Readiness is BLOCKED due to DRC warnings, so CLI exits with code 2,
    # but the output artifacts are still written.
    assert result.exit_code == 2, result.output
    assert "Coverage: 100%" in result.output
    out_dir = dst / "output"
    assert (out_dir / "main.kicad_pcb").exists()
    assert (out_dir / "pin_mapping_report.txt").exists()
    assert (out_dir / "thermal_simulation.csv").exists()
    # main.kicad_pro stays in project root; it is copied into output only
    # when the artifacts are packaged for delivery.
    assert (dst / "main.kicad_pro").exists()
