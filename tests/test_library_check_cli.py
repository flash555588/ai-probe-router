"""Tests for `apr library check` CLI."""

from pathlib import Path

import yaml
from click.testing import CliRunner

from ai_probe_router.cli import main


def _write_valid_library(base: Path) -> None:
    (base / "chips").mkdir(parents=True)
    (base / "modules").mkdir(parents=True)
    (base / "dev_boards").mkdir(parents=True)

    chip = {
        "chip": {
            "mpn": "test_chip",
            "category": "communication",
            "description": "A test chip",
        },
        "power": {
            "domains": [
                {"name": "VDD", "voltage_min": 3.0, "voltage_max": 3.6}
            ]
        },
        "pins": [
            {
                "name": "TX",
                "direction": "output",
                "capabilities": ["UART_TX"],
                "voltage_domain": "VDD",
            }
        ],
    }
    (base / "chips" / "test.yaml").write_text(yaml.safe_dump(chip))

    module = {
        "module": {"name": "test_mod", "type": "test", "version": "1.0.0"},
        "provides": ["TEST"],
        "implementations": [
            {
                "name": "impl",
                "version": "1.0.0",
                "components": [
                    {"type": "mcu", "count": 1, "chip": "test_chip"}
                ],
            }
        ],
    }
    (base / "modules" / "test.yaml").write_text(yaml.safe_dump(module))

    board = {
        "board": {"name": "test_board"},
        "pins": [
            {
                "name": "D0",
                "capabilities": ["GPIO", "UART_TX"],
                "current_ma": 25,
            }
        ],
    }
    (base / "dev_boards" / "test.yaml").write_text(yaml.safe_dump(board))


def test_library_check_valid(tmp_path):
    _write_valid_library(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["library", "check", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "All checks passed" in result.output


def test_library_check_json_format(tmp_path):
    _write_valid_library(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        main, ["library", "check", str(tmp_path), "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    assert '"valid": true' in result.output


def test_library_check_warns_on_schema_issue(tmp_path):
    (tmp_path / "chips").mkdir(parents=True)
    (tmp_path / "modules").mkdir(parents=True)
    (tmp_path / "dev_boards").mkdir(parents=True)
    chip = {
        "chip": {
            "mpn": "test_chip",
            "category": "communication",
            "description": "test",
        },
        "pins": [],
    }
    (tmp_path / "chips" / "test.yaml").write_text(yaml.safe_dump(chip))
    runner = CliRunner()
    result = runner.invoke(main, ["library", "check", str(tmp_path)])
    assert result.exit_code in (0, 2), result.output


def test_library_check_strict_upgrades_exit_code(tmp_path):
    (tmp_path / "chips").mkdir(parents=True)
    (tmp_path / "modules").mkdir(parents=True)
    (tmp_path / "dev_boards").mkdir(parents=True)
    chip = {
        "chip": {
            "mpn": "test_chip",
            "category": "communication",
        },
        "pins": [],
    }
    (tmp_path / "chips" / "test.yaml").write_text(yaml.safe_dump(chip))
    runner = CliRunner()
    result = runner.invoke(main, ["library", "check", str(tmp_path), "--strict"])
    assert result.exit_code == 3, result.output
    assert "INVALID" in result.output


def test_library_check_missing_dir():
    runner = CliRunner()
    result = runner.invoke(main, ["library", "check", "/nonexistent"])
    assert result.exit_code != 0
