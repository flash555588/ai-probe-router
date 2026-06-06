"""Tests for the FastAPI web server."""

from __future__ import annotations

import io
from pathlib import Path

from fastapi.testclient import TestClient

from ai_probe_router.ui.web_server import app

client = TestClient(app)


def test_index_returns_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "AI Probe Router" in response.text


def test_generate_missing_pcb():
    response = client.post("/generate", files={"config": ("c.yaml", io.BytesIO(b""))})
    assert response.status_code == 422


def test_generate_invalid_pcb_extension():
    files = {
        "pcb": ("board.txt", io.BytesIO(b"not a pcb")),
        "config": ("c.yaml", io.BytesIO(b"project:\n  eda_tool: kicad")),
    }
    response = client.post("/generate", files=files)
    assert response.status_code == 400
    assert ".kicad_pcb" in response.json()["detail"]


def test_generate_success(tmp_path: Path):
    # Build minimal PCB
    pcb_text = """(kicad_pcb
  (version 20240108)
  (generator "test")
  (general (thickness 1.6))
  (paper "A4")
  (layers
    (0 "F.Cu" signal)
    (44 "Edge.Cuts" user))
  (net 0 "")
  (net 1 "GND")
  (gr_rect
    (start 0 0)
    (end 50 50)
    (stroke (width 0.1) (type default))
    (fill none)
    (layer "Edge.Cuts")
    (uuid "edge-001"))
)
"""
    config_text = """\
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: ""

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
"""
    files = {
        "pcb": ("main.kicad_pcb", io.BytesIO(pcb_text.encode())),
        "config": ("config.yaml", io.BytesIO(config_text.encode())),
    }
    response = client.post("/generate", files=files)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["ok"] is True
    assert data["coverage_pct"] == 100.0
    assert any(f["name"].endswith(".kicad_pcb") for f in data["files"])
    assert any(f["name"].endswith(".txt") for f in data["files"])
    assert "report" in data


def test_generate_with_schematic(tmp_path: Path):
    pcb_text = """(kicad_pcb
  (version 20240108)
  (generator "test")
  (general (thickness 1.6))
  (paper "A4")
  (layers (0 "F.Cu" signal) (44 "Edge.Cuts" user))
  (net 0 "")
  (net 1 "SIG")
  (gr_rect (start 0 0) (end 50 50)
    (stroke (width 0.1) (type default))
    (fill none) (layer "Edge.Cuts") (uuid "e"))
)
"""
    sch_text = """(kicad_sch
  (version 20231120)
  (generator "test")
  (uuid "root")
  (paper "A4")
)
"""
    config_text = """\
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
  - net: SIG
    role: digital
    required: true
"""
    files = {
        "pcb": ("main.kicad_pcb", io.BytesIO(pcb_text.encode())),
        "sch": ("main.kicad_sch", io.BytesIO(sch_text.encode())),
        "config": ("config.yaml", io.BytesIO(config_text.encode())),
    }
    response = client.post("/generate", files=files)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["ok"] is True
    assert any(f["name"] == "main.kicad_sch" for f in data["files"])
