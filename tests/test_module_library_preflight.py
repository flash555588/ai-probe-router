from pathlib import Path

from ai_probe_router.models.module import FunctionalModule
from ai_probe_router.verification.module_library_preflight_report import (
    ModuleLibraryPreflightReport,
    validate_module_library,
)


def test_default_module_library_preflight_loads():
    result = validate_module_library()

    assert result.ok
    assert result.module_count > 0
    assert result.implementation_count > 0


def test_preflight_reports_missing_required_requested_type(tmp_path):
    _write_module(
        tmp_path / "known.yaml",
        name="known_module",
        module_type="known_type",
    )

    result = validate_module_library(
        [FunctionalModule(name="missing", type="missing_type", required=True)],
        [tmp_path],
    )

    assert not result.ok
    assert "requested module type 'missing_type'" in result.errors[0]


def test_preflight_warns_missing_optional_requested_type(tmp_path):
    _write_module(
        tmp_path / "known.yaml",
        name="known_module",
        module_type="known_type",
    )

    result = validate_module_library(
        [FunctionalModule(name="missing", type="missing_type", required=False)],
        [tmp_path],
    )

    assert result.ok
    assert "requested module type 'missing_type'" in result.warnings[0]


def test_preflight_reports_duplicate_module_name(tmp_path):
    _write_module(tmp_path / "a.yaml", name="dupe", module_type="type_a")
    _write_module(tmp_path / "b.yaml", name="dupe", module_type="type_b")

    result = validate_module_library(library_dirs=[tmp_path])

    assert not result.ok
    assert any("duplicate module name 'dupe'" in error for error in result.errors)


def test_preflight_report_text(tmp_path):
    _write_module(tmp_path / "known.yaml", name="known_module", module_type="known_type")
    result = validate_module_library(library_dirs=[tmp_path])

    text = ModuleLibraryPreflightReport(result).summary_text()

    assert "Module Library Preflight Report" in text
    assert "Modules:" in text


def _write_module(path: Path, *, name: str, module_type: str) -> None:
    path.write_text(
        f"""\
module:
  name: {name}
  type: {module_type}
  version: "1.0.0"

implementations:
  - name: direct
    version: "1.0.0"
    components:
      - type: testpad
        count: 1
    area_mm2: 1
    bom_cost: 0
""",
        encoding="utf-8",
    )
