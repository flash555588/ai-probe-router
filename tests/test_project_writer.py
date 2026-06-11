"""Tests for the KiCad project file writer."""

from __future__ import annotations

import json
from pathlib import Path

from ai_probe_router.eda_adapters.kicad.project_writer import (
    design_rules_from_constraints,
    write_project_file,
)
from ai_probe_router.models.constraints import (
    Constraints,
    ManufacturingRules,
    RoutingRules,
)


def test_design_rules_from_constraints_defaults():
    rules = design_rules_from_constraints(Constraints())
    assert rules["min_track_width"] == 0.15
    assert rules["min_clearance"] == 0.15
    assert rules["min_through_hole_diameter"] == 0.3


def test_design_rules_clearance_takes_stricter_value():
    constraints = Constraints(
        routing=RoutingRules(min_clearance_mm=0.2),
        manufacturing=ManufacturingRules(min_clearance_mm=0.1),
    )
    rules = design_rules_from_constraints(constraints)
    assert rules["min_clearance"] == 0.2


def test_write_project_file_creates_minimal_project(tmp_path: Path):
    pcb = tmp_path / "main.kicad_pcb"
    pro_path = write_project_file(pcb, Constraints())

    assert pro_path == tmp_path / "main.kicad_pro"
    data = json.loads(pro_path.read_text(encoding="utf-8"))
    assert data["board"]["design_settings"]["rules"]["min_track_width"] == 0.15
    assert data["meta"]["filename"] == "main.kicad_pro"


def test_write_project_file_preserves_source_project(tmp_path: Path):
    source = tmp_path / "src.kicad_pro"
    source.write_text(
        json.dumps(
            {
                "board": {
                    "design_settings": {
                        "rules": {"min_track_width": 0.5, "min_silk_clearance": 0.1}
                    }
                },
                "net_settings": {"classes": [{"name": "Default"}]},
            }
        ),
        encoding="utf-8",
    )
    pcb = tmp_path / "out"
    pcb.mkdir()
    pcb = pcb / "main.kicad_pcb"
    pro_path = write_project_file(pcb, Constraints(), source_project=source)

    data = json.loads(pro_path.read_text(encoding="utf-8"))
    rules = data["board"]["design_settings"]["rules"]
    # configured rules override the source, unrelated keys survive
    assert rules["min_track_width"] == 0.15
    assert rules["min_silk_clearance"] == 0.1
    assert data["net_settings"]["classes"][0]["name"] == "Default"
    assert data["meta"]["filename"] == "main.kicad_pro"


def test_write_project_file_tolerates_corrupt_source(tmp_path: Path):
    source = tmp_path / "broken.kicad_pro"
    source.write_text("{not json", encoding="utf-8")
    pcb = tmp_path / "main.kicad_pcb"
    pro_path = write_project_file(pcb, Constraints(), source_project=source)

    data = json.loads(pro_path.read_text(encoding="utf-8"))
    assert data["board"]["design_settings"]["rules"]["min_track_width"] == 0.15
