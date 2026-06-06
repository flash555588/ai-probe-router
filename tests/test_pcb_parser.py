"""Tests for PCB parser — extended coverage including gr_rect."""

from pathlib import Path

from ai_probe_router.eda_adapters.kicad.pcb_parser import parse_pcb

PCB_WITH_GR_RECT = """\
(kicad_pcb
  (version 20240108)
  (generator "test")
  (general (thickness 1.6))
  (paper "A4")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (44 "Edge.Cuts" user))
  (net 0 "")
  (net 1 "GND")
  (footprint "Package_QFP:LQFP-48"
    (layer "F.Cu")
    (at 100 100 0)
    (uuid "abc-123")
    (property "Reference" "U1")
    (property "Value" "STM32")
    (pad "1" smd rect
      (at -5.0 -3.5)
      (size 1.2 0.5)
      (layers "F.Cu" "F.Mask")
      (net 1 "GND")))
  (gr_rect
    (start 80 80)
    (end 120 120)
    (stroke (width 0.1) (type default))
    (fill none)
    (layer "Edge.Cuts")
    (uuid "edge-001"))
)
"""


PCB_WITH_GR_LINE = """\
(kicad_pcb
  (version 20240108)
  (generator "test")
  (general (thickness 1.6))
  (paper "A4")
  (layers (0 "F.Cu" signal) (44 "Edge.Cuts" user))
  (net 0 "")
  (net 1 "GND")
  (gr_line (start 0 0) (end 50 0) (layer "Edge.Cuts") (width 0.1))
  (gr_line (start 50 0) (end 50 50) (layer "Edge.Cuts") (width 0.1))
  (gr_line (start 50 50) (end 0 50) (layer "Edge.Cuts") (width 0.1))
  (gr_line (start 0 50) (end 0 0) (layer "Edge.Cuts") (width 0.1))
)
"""


def test_gr_rect_parsed_as_edges(tmp_path):
    pcb_file = tmp_path / "rect.kicad_pcb"
    pcb_file.write_text(PCB_WITH_GR_RECT)
    board = parse_pcb(pcb_file)
    assert len(board.edges) == 4
    bounds = board.board_bounds()
    assert bounds is not None
    assert bounds.min_x == 80
    assert bounds.min_y == 80
    assert bounds.max_x == 120
    assert bounds.max_y == 120


def test_gr_line_edges(tmp_path):
    pcb_file = tmp_path / "lines.kicad_pcb"
    pcb_file.write_text(PCB_WITH_GR_LINE)
    board = parse_pcb(pcb_file)
    assert len(board.edges) == 4
    bounds = board.board_bounds()
    assert bounds is not None
    assert bounds.width == 50
    assert bounds.height == 50


def test_non_edge_cuts_ignored(tmp_path):
    pcb = """\
(kicad_pcb
  (version 20240108)
  (generator "test")
  (layers (0 "F.Cu" signal) (44 "Edge.Cuts" user))
  (net 0 "")
  (gr_line (start 0 0) (end 50 0) (layer "F.SilkS") (width 0.1))
  (gr_rect (start 10 10) (end 40 40) (layer "F.Fab") (stroke (width 0.1)))
)
"""
    pcb_file = tmp_path / "no_edges.kicad_pcb"
    pcb_file.write_text(pcb)
    board = parse_pcb(pcb_file)
    assert len(board.edges) == 0


PCB_WITH_GR_ARC = """\
(kicad_pcb
  (version 20240108)
  (generator "test")
  (layers (0 "F.Cu" signal) (44 "Edge.Cuts" user))
  (net 0 "")
  (gr_arc (start 0 0) (mid 10 10) (end 20 0) (layer "Edge.Cuts") (width 0.1))
)
"""

PCB_WITH_GR_POLY = """\
(kicad_pcb
  (version 20240108)
  (generator "test")
  (layers (0 "F.Cu" signal) (44 "Edge.Cuts" user))
  (net 0 "")
  (gr_poly
    (pts (xy 0 0) (xy 50 0) (xy 50 50) (xy 0 50))
    (layer "Edge.Cuts")
    (uuid "poly-001"))
)
"""


def test_gr_arc_parsed_as_edges(tmp_path):
    pcb_file = tmp_path / "arc.kicad_pcb"
    pcb_file.write_text(PCB_WITH_GR_ARC)
    board = parse_pcb(pcb_file)
    assert len(board.edges) >= 8
    bounds = board.board_bounds()
    assert bounds is not None
    assert bounds.max_x > 15


def test_gr_poly_parsed_as_edges(tmp_path):
    pcb_file = tmp_path / "poly.kicad_pcb"
    pcb_file.write_text(PCB_WITH_GR_POLY)
    board = parse_pcb(pcb_file)
    assert len(board.edges) == 4
    bounds = board.board_bounds()
    assert bounds is not None
    assert bounds.width == 50
    assert bounds.height == 50


def test_minimal_project_pcb():
    pcb_file = Path(__file__).parent.parent / "examples" / "minimal_project" / "main.kicad_pcb"
    if not pcb_file.exists():
        return
    board = parse_pcb(pcb_file)
    assert len(board.nets) >= 7
    assert len(board.footprints) >= 1
    assert len(board.edges) == 4
    bounds = board.board_bounds()
    assert bounds is not None
    assert abs(bounds.width - 40) < 0.01
    assert abs(bounds.height - 40) < 0.01
