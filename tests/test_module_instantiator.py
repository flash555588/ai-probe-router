from ai_probe_router.config import ProjectConfig
from ai_probe_router.models.board import Schematic
from ai_probe_router.models.module import FunctionalModule
from ai_probe_router.solvers.module_graph import build_module_graph
from ai_probe_router.solvers.module_selector import select_modules
from ai_probe_router.synthesis.module_instantiator import instantiate_module_sheets
from ai_probe_router.verification.module_instantiation_report import ModuleInstantiationReport


def _schematic() -> Schematic:
    return Schematic(
        raw=[
            "kicad_sch",
            ["version", "20231120"],
            ["generator", "eeschema"],
            ["uuid", "root"],
            ["paper", "A4"],
            ["lib_symbols"],
        ],
    )


def _graph():
    modules = [
        FunctionalModule(
            name="debug_access",
            type="debug_swd",
            target_nets=["SWDIO", "SWCLK"],
            rails=["VDD_3V3"],
        ),
    ]
    cfg = ProjectConfig(schema_version=2, functional_modules=modules)
    return build_module_graph(cfg, select_modules(modules)).graph


def test_module_instantiator_adds_parent_sheet_and_child_file(tmp_path):
    sch = _schematic()

    result = instantiate_module_sheets(sch, _graph(), tmp_path)

    assert not result.skipped
    assert len(result.sheets) == 1
    assert any(isinstance(node, list) and node[0] == "sheet" for node in sch.raw)
    child = tmp_path / result.sheets[0].sheet_file
    assert child.exists()
    text = child.read_text(encoding="utf-8")
    assert "SWDIO" in text
    assert "APR_GENERATED" in text


def test_module_instantiator_skips_without_schematic(tmp_path):
    result = instantiate_module_sheets(None, _graph(), tmp_path)

    assert result.skipped
    assert result.skip_reason == "no_schematic"


def test_module_instantiation_report_text(tmp_path):
    sch = _schematic()
    result = instantiate_module_sheets(sch, _graph(), tmp_path)

    text = ModuleInstantiationReport(result).summary_text()

    assert "Module Instantiation Report" in text
    assert "generated_modules" in text

