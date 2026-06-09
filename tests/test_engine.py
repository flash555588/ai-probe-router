"""Integration test: full engine pipeline."""

import json
import math
import shutil
from pathlib import Path

from ai_probe_router.config import load_config
from ai_probe_router.eda_adapters.kicad.cli_runner import CheckResult
from ai_probe_router.engine import run
from ai_probe_router.pipeline.native_tools import NativeValidationResult
from ai_probe_router.routing.freerouting_bridge import RoutingResult


def test_engine_phase1(tmp_path):
    examples = Path(__file__).parent.parent / "examples"
    config_src = examples / "sample_config.yaml"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"
    if not all(p.exists() for p in [config_src, pcb_src, sch_src]):
        return

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")
    shutil.copy(config_src, tmp_path / "config.yaml")

    cfg = load_config(tmp_path / "config.yaml")
    report, pin_report = run(cfg, tmp_path)

    assert report.total_nets_requested == 9
    assert report.covered > 0
    assert report.coverage_pct > 0

    out_dir = tmp_path / "output"
    assert out_dir.exists()
    assert (out_dir / "main.kicad_pcb").exists()
    assert (out_dir / "main.kicad_sch").exists()
    assert (out_dir / "testpoint_report.txt").exists()


def test_engine_phase1_coverage_100(tmp_path):
    examples = Path(__file__).parent.parent / "examples"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"
    if not all(p.exists() for p in [pcb_src, sch_src]):
        return

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")

    config_yaml = """\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

probe_interface:
  type: test_pad
  side: top
  pad_diameter_mm: 1.5
  min_probe_spacing_mm: 2.54
  preferred_grid_mm: 2.54

nets_to_expose:
  - net: SWDIO
    role: debug
    required: true
  - net: GND
    role: ground
    required: true
"""
    (tmp_path / "config.yaml").write_text(config_yaml)
    cfg = load_config(tmp_path / "config.yaml")
    report, _ = run(cfg, tmp_path)
    assert report.coverage_pct == 100.0
    assert report.covered == 2


def test_engine_constraint_validation(tmp_path):
    examples = Path(__file__).parent.parent / "examples"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"
    if not all(p.exists() for p in [pcb_src, sch_src]):
        return

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")

    config_yaml = """\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

probe_interface:
  type: test_pad
  side: top
  pad_diameter_mm: 1.5
  min_probe_spacing_mm: 2.54
  preferred_grid_mm: 2.54

nets_to_expose:
  - net: SWDIO
    role: debug
    required: true

placement_rules:
  min_distance_from_board_edge_mm: 2.0
"""
    (tmp_path / "config.yaml").write_text(config_yaml)
    cfg = load_config(tmp_path / "config.yaml")
    report, _ = run(cfg, tmp_path)
    assert report.constraint_ok is not None


def test_engine_protection_circuits(tmp_path):
    examples = Path(__file__).parent.parent / "examples"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"
    if not all(p.exists() for p in [pcb_src, sch_src]):
        return

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")

    config_yaml = """\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

probe_interface:
  type: test_pad
  side: top
  pad_diameter_mm: 1.5
  min_probe_spacing_mm: 2.54
  preferred_grid_mm: 2.54

nets_to_expose:
  - net: SWDIO
    role: debug
    required: true
  - net: NRST
    role: reset
    required: false
  - net: GND
    role: ground
    required: true

protection:
  enabled: true
  debug:
    type: series_resistor
    value: "33"
    package: "0402"
  reset:
    type: series_resistor
    value: "100"
    package: "0402"
"""
    (tmp_path / "config.yaml").write_text(config_yaml)
    cfg = load_config(tmp_path / "config.yaml")
    assert cfg.protection.enabled
    assert cfg.protection.get_protection("debug") is not None
    assert cfg.protection.get_protection("reset") is not None
    assert cfg.protection.get_protection("ground") is None

    report, _ = run(cfg, tmp_path)
    assert report.covered >= 2

    out_pcb = (tmp_path / "output" / "main.kicad_pcb").read_text(encoding="utf-8")
    assert "PROBE_SWDIO" in out_pcb
    assert "PROBE_NRST" in out_pcb
    assert "PROBE_GND" not in out_pcb


def test_engine_writes_json_thermal_export(tmp_path):
    examples = Path(__file__).parent.parent / "examples"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"
    if not all(p.exists() for p in [pcb_src, sch_src]):
        return

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")

    config_yaml = """\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

hardware_platform:
  target_voltage_domains:
    - name: 3V3
      voltage: 3.3

probe_interface:
  type: test_pad

nets_to_expose:
  - net: 3V3
    role: power
    current_ma: 250

thermal_analysis:
  enabled: true
  output_format: json
"""
    (tmp_path / "config.yaml").write_text(config_yaml, encoding="utf-8")
    cfg = load_config(tmp_path / "config.yaml")

    run(cfg, tmp_path)

    thermal_path = tmp_path / "output" / "thermal_simulation.json"
    payload = json.loads(thermal_path.read_text(encoding="utf-8"))
    assert payload["thermal_analysis"]["enabled"]
    assert any(row["net_name"] == "3V3" for row in payload["rows"])
    row = next(row for row in payload["rows"] if row["net_name"] == "3V3")
    assert row["estimated_power_mw"] == 825.0
    assert row["risk"] == "medium"


def test_engine_places_paired_probe_near_existing_mate(tmp_path):
    examples = Path(__file__).parent.parent / "examples"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"
    if not all(p.exists() for p in [pcb_src, sch_src]):
        return

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")

    config_yaml = """\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

probe_interface:
  type: test_pad
  side: top
  pad_diameter_mm: 1.0
  min_probe_spacing_mm: 2.54
  preferred_grid_mm: 2.54

nets_to_expose:
  - net: SWDIO
    role: high_speed
    pair_with: SWCLK
  - net: SWCLK
    role: high_speed
    pair_with: SWDIO
"""
    (tmp_path / "config.yaml").write_text(config_yaml, encoding="utf-8")

    report, _ = run(load_config(tmp_path / "config.yaml"), tmp_path)

    swdio = next(entry for entry in report.entries if entry.net_name == "SWDIO")
    swclk = next(entry for entry in report.entries if entry.net_name == "SWCLK")
    assert swdio.has_testpoint
    assert swclk.has_testpoint
    assert math.hypot(
        swdio.probe_x - swclk.probe_x,
        swdio.probe_y - swclk.probe_y,
    ) <= 8.0


def test_engine_records_manufacturing_export_failures_in_soft_mode(
    tmp_path,
    monkeypatch,
):
    examples = Path(__file__).parent.parent / "examples"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"
    if not all(p.exists() for p in [pcb_src, sch_src]):
        return

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")
    _write_export_contract_config(tmp_path, "")

    failed = CheckResult(ok=None, error="kicad-cli not found")
    monkeypatch.setattr(
        "ai_probe_router.pipeline.native_tools.export_gerbers",
        lambda *args: failed,
    )
    monkeypatch.setattr(
        "ai_probe_router.pipeline.native_tools.export_drill",
        lambda *args: failed,
    )
    monkeypatch.setattr(
        "ai_probe_router.pipeline.native_tools.export_pos",
        lambda *args: failed,
    )

    report, _ = run(load_config(tmp_path / "config.yaml"), tmp_path)

    assert any("Gerber export failed: kicad-cli not found" in note for note in report.notes)
    assert any("Drill export failed: kicad-cli not found" in note for note in report.notes)
    assert any("Pick&Place export failed: kicad-cli not found" in note for note in report.notes)


def test_engine_strict_signoff_blocks_manufacturing_export_failure(
    tmp_path,
    monkeypatch,
):
    examples = Path(__file__).parent.parent / "examples"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"
    if not all(p.exists() for p in [pcb_src, sch_src]):
        return

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")
    _write_export_contract_config(tmp_path, "  strict_signoff: true\n")

    monkeypatch.setattr(
        "ai_probe_router.engine.run_native_validation",
        lambda *args: NativeValidationResult(
            drc=CheckResult(ok=True),
            erc=CheckResult(ok=True),
        ),
    )
    monkeypatch.setattr(
        "ai_probe_router.pipeline.native_tools.export_gerbers",
        lambda *args: CheckResult(ok=False, error="gerber failed"),
    )

    try:
        run(load_config(tmp_path / "config.yaml"), tmp_path)
    except RuntimeError as exc:
        assert "Gerber export failed: gerber failed" in str(exc)
    else:
        raise AssertionError("strict_signoff should block failed Gerber export")


def test_engine_strict_signoff_blocks_native_validation_failure(
    tmp_path,
    monkeypatch,
):
    examples = Path(__file__).parent.parent / "examples"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"
    if not all(p.exists() for p in [pcb_src, sch_src]):
        return

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")
    _write_export_contract_config(tmp_path, "  strict_signoff: true\n")

    monkeypatch.setattr(
        "ai_probe_router.engine.run_native_validation",
        lambda *args: NativeValidationResult(
            drc=CheckResult(ok=False, error="native DRC failed"),
        ),
    )

    try:
        run(load_config(tmp_path / "config.yaml"), tmp_path)
    except RuntimeError as exc:
        assert "DRC validation failed: native DRC failed" in str(exc)
    else:
        raise AssertionError("strict_signoff should block failed native validation")


def test_engine_required_manufacturing_exports_block_failure(
    tmp_path,
    monkeypatch,
):
    examples = Path(__file__).parent.parent / "examples"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"
    if not all(p.exists() for p in [pcb_src, sch_src]):
        return

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")
    _write_export_contract_config(
        tmp_path,
        "  require_manufacturing_exports: true\n",
    )

    monkeypatch.setattr(
        "ai_probe_router.pipeline.native_tools.export_gerbers",
        lambda *args: CheckResult(ok=False, error="gerber failed"),
    )

    try:
        run(load_config(tmp_path / "config.yaml"), tmp_path)
    except RuntimeError as exc:
        assert "Gerber export failed: gerber failed" in str(exc)
    else:
        raise AssertionError("required manufacturing exports should block failed export")


def test_engine_records_autorouter_failure_in_soft_mode(tmp_path, monkeypatch):
    examples = Path(__file__).parent.parent / "examples"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"
    if not all(p.exists() for p in [pcb_src, sch_src]):
        return

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")
    _write_export_contract_config(tmp_path, "  require_autorouter_feedback: false\n")

    def fake_autorouter(cfg, coverage, *_args, **_kwargs):
        result = RoutingResult(error="FreeRouting not found")
        coverage.notes.append("Auto-route failed: FreeRouting not found")
        return result

    monkeypatch.setattr("ai_probe_router.engine.run_autorouter", fake_autorouter)

    report, _ = run(load_config(tmp_path / "config.yaml"), tmp_path)

    assert any("Auto-route failed: FreeRouting not found" in note for note in report.notes)
    process = (tmp_path / "output" / "design_process_report.txt").read_text(
        encoding="utf-8",
    )
    assert "autorouter_feedback_missing" in process


def test_engine_required_autorouter_feedback_blocks_failure(tmp_path, monkeypatch):
    examples = Path(__file__).parent.parent / "examples"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"
    if not all(p.exists() for p in [pcb_src, sch_src]):
        return

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")
    _write_export_contract_config(tmp_path, "  require_autorouter_feedback: true\n")

    def fake_autorouter(*_args, **_kwargs):
        raise RuntimeError("Auto-route failed: FreeRouting failed")

    monkeypatch.setattr("ai_probe_router.engine.run_autorouter", fake_autorouter)

    try:
        run(load_config(tmp_path / "config.yaml"), tmp_path)
    except RuntimeError as exc:
        assert "Auto-route failed: FreeRouting failed" in str(exc)
    else:
        raise AssertionError("required autorouter feedback should block failed autoroute")


def test_engine_writes_module_report_for_schema_v2(tmp_path):
    config_yaml = """\
schema_version: 2

project:
  eda_tool: kicad
  board_file: ""
  schematic_file: ""

functional_modules:
  - name: power_observation
    type: current_voltage_monitor
    required: true
    rails: [VDD_3V3]
    telemetry_bus: i2c

resource_allocator:
  enable: true
"""
    (tmp_path / "config.yaml").write_text(config_yaml, encoding="utf-8")
    cfg = load_config(tmp_path / "config.yaml")

    report, _ = run(cfg, tmp_path)

    assert report.total_nets_requested == 0
    module_report = tmp_path / "output" / "module_report.txt"
    assert module_report.exists()
    assert "power_observation" in module_report.read_text(encoding="utf-8")
    assert (tmp_path / "output" / "module_library_preflight_report.txt").exists()
    assert (tmp_path / "output" / "module_graph_report.txt").exists()
    assert (tmp_path / "output" / "module_compatibility_report.txt").exists()
    assert (tmp_path / "output" / "bus_report.txt").exists()
    assert (tmp_path / "output" / "power_report.txt").exists()
    assert (tmp_path / "output" / "routing_feasibility_report.txt").exists()
    assert (tmp_path / "output" / "module_placement_report.txt").exists()
    assert (tmp_path / "output" / "resource_allocation_report.json").exists()
    assert (tmp_path / "output" / "resource_optimization_report.json").exists()
    assert (tmp_path / "output" / "readiness_report.txt").exists()
    assert (tmp_path / "output" / "design_process_report.txt").exists()
    manifest = tmp_path / "output" / "decision_manifest.json"
    assert manifest.exists()
    assert '"run_id": "APR-' in manifest.read_text(encoding="utf-8")
    readiness = (tmp_path / "output" / "readiness_report.txt").read_text(encoding="utf-8")
    assert "Run ID:    APR-" in readiness
    assert "Run ID:           APR-" in (
        tmp_path / "output" / "testpoint_report.txt"
    ).read_text(encoding="utf-8")
    instantiation = tmp_path / "output" / "module_instantiation_report.txt"
    assert instantiation.exists()
    assert "SKIPPED (no_schematic)" in instantiation.read_text(encoding="utf-8")
    bom = tmp_path / "output" / "bom_report.csv"
    assert bom.exists()
    bom_text = bom.read_text(encoding="utf-8")
    assert "run_id,module_id,module_name" in bom_text
    assert "APR-" in bom_text


def test_engine_blocks_generation_on_module_graph_error(tmp_path):
    examples = Path(__file__).parent.parent / "examples"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"
    if not all(p.exists() for p in [pcb_src, sch_src]):
        return

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")

    config_yaml = """\
schema_version: 2

project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

functional_modules:
  - name: fixture
    type: protected_probe_fixture
    depends_on: [debug]

nets_to_expose:
  - net: SWDIO
    role: debug
    required: true
"""
    (tmp_path / "config.yaml").write_text(config_yaml, encoding="utf-8")
    cfg = load_config(tmp_path / "config.yaml")

    report, pin_report = run(cfg, tmp_path)

    out_dir = tmp_path / "output"
    assert pin_report is None
    assert report.missing == 1
    assert (out_dir / "module_graph_report.txt").exists()
    assert "depends on missing module" in (
        out_dir / "module_graph_report.txt"
    ).read_text(encoding="utf-8")
    readiness = (out_dir / "readiness_report.txt").read_text(encoding="utf-8")
    assert "Verdict:   BLOCKED" in readiness
    assert not (out_dir / "main.kicad_pcb").exists()
    assert not (out_dir / "main.kicad_sch").exists()


def test_engine_blocks_generation_on_module_preflight_error(tmp_path):
    examples = Path(__file__).parent.parent / "examples"
    pcb_src = examples / "minimal_project" / "main.kicad_pcb"
    sch_src = examples / "minimal_project" / "main.kicad_sch"
    if not all(p.exists() for p in [pcb_src, sch_src]):
        return

    shutil.copy(pcb_src, tmp_path / "main.kicad_pcb")
    shutil.copy(sch_src, tmp_path / "main.kicad_sch")

    config_yaml = """\
schema_version: 2

project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

functional_modules:
  - name: impossible_module
    type: not_in_library
    required: true

nets_to_expose:
  - net: SWDIO
    role: debug
    required: true
"""
    (tmp_path / "config.yaml").write_text(config_yaml, encoding="utf-8")
    cfg = load_config(tmp_path / "config.yaml")

    report, pin_report = run(cfg, tmp_path)

    out_dir = tmp_path / "output"
    assert pin_report is None
    assert report.missing == 1
    preflight = (out_dir / "module_library_preflight_report.txt").read_text(
        encoding="utf-8",
    )
    assert "requested module type 'not_in_library'" in preflight
    readiness = (out_dir / "readiness_report.txt").read_text(encoding="utf-8")
    assert "Verdict:   BLOCKED" in readiness
    assert "module_library_preflight" in readiness
    assert not (out_dir / "module_report.txt").exists()
    assert not (out_dir / "main.kicad_pcb").exists()


def _write_export_contract_config(tmp_path: Path, process_controls: str) -> None:
    config_yaml = f"""\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

probe_interface:
  type: test_pad
  side: top
  pad_diameter_mm: 1.5
  min_probe_spacing_mm: 2.54
  preferred_grid_mm: 2.54
  require_silkscreen_labels: false
  require_fiducials: false
  require_tooling_holes: false

nets_to_expose:
  - net: SWDIO
    role: debug
    required: true

process_controls:
{process_controls or "  strict_signoff: false\n"}
"""
    (tmp_path / "config.yaml").write_text(config_yaml, encoding="utf-8")
