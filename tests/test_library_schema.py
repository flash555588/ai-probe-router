"""Tests for library schema validation layers."""

from pathlib import Path

import pytest
import yaml

from ai_probe_router.library.checker import (
    LibraryChecker,
    ValidationIssue,
    ValidationSeverity,
)
from ai_probe_router.library.report import LibraryCheckReport
from ai_probe_router.library.schema_loader import SchemaLoader


@pytest.fixture
def schema_loader():
    return SchemaLoader()


def test_schema_loader_finds_schemas(schema_loader):
    schemas = schema_loader.all_schemas()
    assert set(schemas.keys()) == {"chip", "module", "dev_board", "project_config"}


def test_schema_loader_loads_chip_schema(schema_loader):
    schema = schema_loader.load("chip")
    assert schema["title"] == "Chip Definition"
    assert "chip" in schema["required"]


def test_schema_loader_loads_module_schema(schema_loader):
    schema = schema_loader.load("module")
    assert schema["title"] == "Module Definition"
    assert "implementations" in schema["required"]


def test_schema_loader_loads_dev_board_schema(schema_loader):
    schema = schema_loader.load("dev_board")
    assert schema["title"] == "Development Board Definition"
    assert "board" in schema["required"]


def test_schema_loader_unknown_name_raises():
    with pytest.raises(KeyError):
        SchemaLoader().load("unknown")


def _mkdirs(base: Path) -> None:
    (base / "chips").mkdir(exist_ok=True)
    (base / "modules").mkdir(exist_ok=True)
    (base / "dev_boards").mkdir(exist_ok=True)


class TestJsonSchemaLayer:
    def test_valid_chip_passes(self, tmp_path):
        _mkdirs(tmp_path)
        chip_file = tmp_path / "chips" / "chip.yaml"
        chip_file.write_text(
            yaml.safe_dump(
                {
                    "chip": {
                        "mpn": "test_chip",
                        "category": "communication",
                        "description": "A test chip",
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
            )
        )
        checker = LibraryChecker(tmp_path)
        checker._check_json_schema_layer()
        assert not checker.issues

    def test_missing_required_field_warns(self, tmp_path):
        _mkdirs(tmp_path)
        chip_file = tmp_path / "chips" / "chip.yaml"
        chip_file.write_text(
            yaml.safe_dump({"chip": {"mpn": "test", "category": "communication"}})
        )
        checker = LibraryChecker(tmp_path)
        checker._check_json_schema_layer()
        issues = [i for i in checker.issues if i.layer == "json_schema"]
        assert len(issues) >= 1

    def test_invalid_enum_value_warns(self, tmp_path):
        _mkdirs(tmp_path)
        chip_file = tmp_path / "chips" / "chip.yaml"
        chip_file.write_text(
            yaml.safe_dump(
                {
                    "chip": {
                        "mpn": "test",
                        "category": "not_a_category",
                        "description": "test",
                    },
                    "pins": [],
                }
            )
        )
        checker = LibraryChecker(tmp_path)
        checker._check_json_schema_layer()
        issues = [i for i in checker.issues if "category" in i.message]
        assert len(issues) >= 1

    def test_strict_mode_upgrades_warnings(self, tmp_path):
        _mkdirs(tmp_path)
        chip_file = tmp_path / "chips" / "chip.yaml"
        chip_file.write_text(
            yaml.safe_dump({"chip": {"mpn": "test", "category": "communication"}})
        )
        checker = LibraryChecker(tmp_path, strict=True)
        checker._check_json_schema_layer()
        schema_issues = [i for i in checker.issues if i.layer == "json_schema"]
        assert all(i.severity == ValidationSeverity.ERROR for i in schema_issues)

    def test_empty_yaml_file_error(self, tmp_path):
        _mkdirs(tmp_path)
        chip_file = tmp_path / "chips" / "chip.yaml"
        chip_file.write_text("")
        checker = LibraryChecker(tmp_path)
        checker._check_json_schema_layer()
        issues = [i for i in checker.issues if i.layer == "json_schema"]
        assert any("Empty" in i.message for i in issues)


class TestSemanticLayer:
    def test_chip_pin_unknown_voltage_domain_warns(self, tmp_path):
        _mkdirs(tmp_path)
        chip_file = tmp_path / "chips" / "chip.yaml"
        chip_file.write_text(
            yaml.safe_dump(
                {
                    "chip": {
                        "mpn": "test",
                        "category": "communication",
                        "description": "test",
                    },
                    "pins": [
                        {
                            "name": "TX",
                            "direction": "output",
                            "capabilities": ["UART_TX"],
                            "voltage_domain": "UNKNOWN_DOMAIN",
                        }
                    ],
                }
            )
        )
        checker = LibraryChecker(tmp_path)
        checker._check_semantic_layer()
        issues = [i for i in checker.issues if i.layer == "semantic"]
        assert any("UNKNOWN_DOMAIN" in i.message for i in issues)

    def test_module_unknown_chip_warns(self, tmp_path):
        _mkdirs(tmp_path)
        chip_file = tmp_path / "chips" / "known.yaml"
        chip_file.write_text(
            yaml.safe_dump(
                {
                    "chip": {
                        "mpn": "known_chip",
                        "category": "communication",
                        "description": "test",
                    },
                    "pins": [],
                }
            )
        )
        mod_file = tmp_path / "modules" / "mod.yaml"
        mod_file.write_text(
            yaml.safe_dump(
                {
                    "module": {"name": "mod", "type": "test", "version": "1.0"},
                    "provides": ["TEST"],
                    "implementations": [
                        {
                            "name": "impl",
                            "version": "1.0",
                            "components": [
                                {"type": "mcu", "count": 1, "chip": "unknown_chip"}
                            ],
                        }
                    ],
                }
            )
        )
        checker = LibraryChecker(tmp_path)
        checker._check_semantic_layer()
        issues = [i for i in checker.issues if i.layer == "semantic"]
        assert any("unknown_chip" in i.message for i in issues)

    def test_i2c_address_out_of_range_warns(self, tmp_path):
        _mkdirs(tmp_path)
        mod_file = tmp_path / "modules" / "mod.yaml"
        mod_file.write_text(
            yaml.safe_dump(
                {
                    "module": {"name": "mod", "type": "test", "version": "1.0"},
                    "provides": ["TEST"],
                    "implementations": [
                        {
                            "name": "impl",
                            "version": "1.0",
                            "components": [],
                            "constraints": {"i2c_address": "0x05"},
                        }
                    ],
                }
            )
        )
        checker = LibraryChecker(tmp_path)
        checker._check_semantic_layer()
        issues = [i for i in checker.issues if i.layer == "semantic"]
        assert any("0x5" in i.message for i in issues)

    def test_dev_board_ground_without_gnd_capability_warns(self, tmp_path):
        _mkdirs(tmp_path)
        board_file = tmp_path / "dev_boards" / "board.yaml"
        board_file.write_text(
            yaml.safe_dump(
                {
                    "board": {"name": "test_board"},
                    "pins": [
                        {
                            "name": "GND",
                            "capabilities": ["POWER_3V3"],
                            "current_ma": 1000,
                            "is_ground": True,
                        }
                    ],
                }
            )
        )
        checker = LibraryChecker(tmp_path)
        checker._check_semantic_layer()
        issues = [i for i in checker.issues if i.layer == "semantic"]
        assert any("is_ground" in i.message for i in issues)


class TestCompatibilityLayer:
    def test_module_package_not_on_chip_warns(self, tmp_path):
        _mkdirs(tmp_path)
        chip_file = tmp_path / "chips" / "chip.yaml"
        chip_file.write_text(
            yaml.safe_dump(
                {
                    "chip": {
                        "mpn": "test_chip",
                        "category": "communication",
                        "description": "test",
                    },
                    "package_options": [{"name": "QFN-32", "footprint": "fp"}],
                    "pins": [],
                }
            )
        )
        mod_file = tmp_path / "modules" / "mod.yaml"
        mod_file.write_text(
            yaml.safe_dump(
                {
                    "module": {"name": "mod", "type": "test", "version": "1.0"},
                    "provides": ["TEST"],
                    "implementations": [
                        {
                            "name": "impl",
                            "version": "1.0",
                            "components": [
                                {
                                    "type": "mcu",
                                    "count": 1,
                                    "chip": "test_chip",
                                    "package_options": ["BGA-100"],
                                }
                            ],
                        }
                    ],
                }
            )
        )
        checker = LibraryChecker(tmp_path)
        checker._check_compatibility_layer()
        issues = [i for i in checker.issues if i.layer == "compatibility"]
        assert any("BGA-100" in i.message for i in issues)


class TestReport:
    def test_valid_report(self):
        report = LibraryCheckReport(issues=[])
        assert report.valid
        assert report.exit_code == 0
        assert "All checks passed" in report.to_text()

    def test_warning_report(self):
        report = LibraryCheckReport(
            issues=[
                ValidationIssue(
                    ValidationSeverity.WARNING, "semantic", Path("x.yaml"), "warn", field="f"
                )
            ]
        )
        assert report.valid
        assert report.exit_code == 2
        assert "VALID_WITH_WARNINGS" in report.to_text()

    def test_error_report(self):
        report = LibraryCheckReport(
            issues=[
                ValidationIssue(
                    ValidationSeverity.ERROR, "json_schema", Path("x.yaml"), "err", field="f"
                )
            ]
        )
        assert not report.valid
        assert report.exit_code == 3
        assert "INVALID" in report.to_text()

    def test_json_output(self):
        report = LibraryCheckReport(issues=[])
        data = report.to_dict()
        assert data["valid"] is True
        assert data["exit_code"] == 0

    def test_write_files(self, tmp_path):
        report = LibraryCheckReport(issues=[])
        text_path = tmp_path / "report.txt"
        json_path = tmp_path / "report.json"
        report.write(text_path, json_path)
        assert text_path.exists()
        assert json_path.exists()
