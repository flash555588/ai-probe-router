"""Golden-output regression tests for the minimal project."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from ai_probe_router.config import load_config
from ai_probe_router.eda_adapters.kicad.cli_runner import CheckResult
from ai_probe_router.engine import run
from ai_probe_router.routing.freerouting_bridge import RoutingResult

GOLDEN_DIR = Path(__file__).parent / "golden" / "minimal_project"
UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
)
RUN_ID_RE = re.compile(r"APR-[A-F0-9]{12}")


def test_minimal_project_golden_outputs(tmp_path, monkeypatch):
    project = tmp_path / "project"
    _copy_minimal_project(project)
    _stub_external_tools(monkeypatch)
    cfg_path = project / "config.yaml"
    cfg_path.write_text(_golden_config(), encoding="utf-8")

    cfg = load_config(cfg_path)
    run(cfg, project)

    output_dir = project / "output"
    for name in (
        "main.kicad_pcb",
        "main.kicad_sch",
        "testpoint_report.txt",
        "readiness_report.json",
        "decision_manifest.json",
    ):
        actual = _normalized_output(output_dir / name)
        expected = (GOLDEN_DIR / name).read_text(encoding="utf-8")
        assert actual == expected


def _copy_minimal_project(project: Path) -> None:
    source = Path(__file__).parent.parent / "examples" / "minimal_project"
    project.mkdir()
    shutil.copy(source / "main.kicad_pcb", project / "main.kicad_pcb")
    shutil.copy(source / "main.kicad_sch", project / "main.kicad_sch")


def _stub_external_tools(monkeypatch) -> None:
    check = CheckResult(ok=None, error="not available in golden test")
    monkeypatch.setattr("ai_probe_router.engine.run_drc", lambda *_args, **_kw: check)
    monkeypatch.setattr("ai_probe_router.engine.run_erc", lambda *_args, **_kw: check)
    monkeypatch.setattr("ai_probe_router.engine.export_gerbers", lambda *_args, **_kw: check)
    monkeypatch.setattr("ai_probe_router.engine.export_drill", lambda *_args, **_kw: check)
    monkeypatch.setattr("ai_probe_router.engine.export_pos", lambda *_args, **_kw: check)
    monkeypatch.setattr(
        "ai_probe_router.engine.run_freerouting_route",
        lambda *_args, **_kw: RoutingResult(
            error="not available in golden test",
            duration_sec=0.0,
        ),
    )


def _normalized_output(path: Path) -> str:
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return json.dumps(_normalize_json(payload), indent=2, sort_keys=True) + "\n"
    text = path.read_text(encoding="utf-8")
    text = UUID_RE.sub("UUID", text)
    text = RUN_ID_RE.sub("APR-RUNID", text)
    return text.replace("\r\n", "\n")


def _normalize_json(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        return {
            item_key: _normalize_json(item_value, item_key)
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [_normalize_json(item) for item in value]
    if key == "run_id" and isinstance(value, str):
        return RUN_ID_RE.sub("APR-RUNID", value)
    if key == "sha1":
        return "SHA1"
    if key == "python":
        return "PYTHON"
    if key == "platform":
        return "PLATFORM"
    if key == "duration_sec":
        return 0.0
    return value


def _golden_config() -> str:
    return """\
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
  - net: GND
    role: ground
    required: true
  - net: SWDIO
    role: debug
    required: true
"""
