from ai_probe_router.config import ProjectConfig
from ai_probe_router.models.module import FunctionalModule
from ai_probe_router.solvers.module_graph import build_module_graph
from ai_probe_router.solvers.module_selector import select_modules
from ai_probe_router.verification.bom_report import BomReport
from ai_probe_router.verification.module_compatibility_report import (
    ModuleCompatibilityReport,
    analyze_module_compatibility,
)


def _build(modules):
    cfg = ProjectConfig(schema_version=2, functional_modules=modules)
    selection = select_modules(modules)
    return build_module_graph(cfg, selection)


def test_module_compatibility_reports_versions_and_alternates():
    graph = _build([
        FunctionalModule(
            name="analog",
            type="analog_measurement",
            version="1.0.0",
        ),
    ])

    result = analyze_module_compatibility(graph)
    text = ModuleCompatibilityReport(result).summary_text()

    assert result.ok
    assert any(row.chip_version == "1.0.0" for row in result.rows)
    assert any("generic_i2c_adc_12bit_alt" in row.alternate_chips for row in result.rows)
    assert "Module Compatibility Report" in text
    assert "module=1.0.0" in text


def test_module_compatibility_reports_requested_version_mismatch():
    graph = _build([
        FunctionalModule(
            name="analog",
            type="analog_measurement",
            version="9.9.9",
        ),
    ])

    result = analyze_module_compatibility(graph)

    assert not graph.ok
    assert not result.ok
    assert "requested module version 9.9.9" in result.errors[0]


def test_bom_report_includes_version_and_alternate_columns(tmp_path):
    graph = _build([
        FunctionalModule(
            name="analog",
            type="analog_measurement",
            version="1.0.0",
        ),
    ])

    path = tmp_path / "bom_report.csv"
    BomReport(graph, run_id="APR-TEST").write(path)
    text = path.read_text(encoding="utf-8")

    assert text.startswith("run_id,module_id")
    assert "APR-TEST,MOD1,analog" in text
    assert "implementation_version" in text
    assert "chip_version" in text
    assert "alternate_chips" in text
    assert "generic_i2c_adc_12bit_alt" in text
