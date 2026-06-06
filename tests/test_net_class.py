"""Tests for net_class insertion into KiCad PCB."""

from __future__ import annotations

from pathlib import Path

from ai_probe_router.eda_adapters.kicad.pcb_parser import parse_pcb
from ai_probe_router.eda_adapters.kicad.pcb_writer import add_net_class, write_pcb

MINIMAL_PCB = """\
(kicad_pcb
  (version 20240108)
  (generator "test")
  (general (thickness 1.6))
  (paper "A4")
  (layers
    (0 "F.Cu" signal)
    (44 "Edge.Cuts" user))
  (net 0 "")
)
"""


def test_add_net_class_at_root(tmp_path: Path):
    pcb_file = tmp_path / "test.kicad_pcb"
    pcb_file.write_text(MINIMAL_PCB)
    board = parse_pcb(pcb_file)

    add_net_class(board, "Power", clearance=0.2, trace_width=0.5)

    class_nodes = [n for n in board.raw if isinstance(n, list) and n[0] == "net_class"]
    assert len(class_nodes) == 1
    assert class_nodes[0][1] == "Power"
    assert ["clearance", "0.2"] in class_nodes[0]
    assert ["trace_width", "0.5"] in class_nodes[0]


def test_add_net_class_updates_existing(tmp_path: Path):
    pcb_file = tmp_path / "test.kicad_pcb"
    pcb_file.write_text(MINIMAL_PCB)
    board = parse_pcb(pcb_file)

    add_net_class(board, "Signal", clearance=0.15, trace_width=0.15)
    add_net_class(board, "Signal", clearance=0.25, trace_width=0.2)

    class_nodes = [n for n in board.raw if isinstance(n, list) and n[0] == "net_class"]
    assert len(class_nodes) == 1
    assert ["clearance", "0.25"] in class_nodes[0]
    assert ["trace_width", "0.2"] in class_nodes[0]


def test_add_net_class_with_diff_pair(tmp_path: Path):
    pcb_file = tmp_path / "test.kicad_pcb"
    pcb_file.write_text(MINIMAL_PCB)
    board = parse_pcb(pcb_file)

    add_net_class(
        board, "USB", clearance=0.2, trace_width=0.15,
        diff_pair_width=0.15, diff_pair_gap=0.25,
    )

    nc = [n for n in board.raw if isinstance(n, list) and n[0] == "net_class"][0]
    assert ["diff_pair_width", "0.15"] in nc
    assert ["diff_pair_gap", "0.25"] in nc


def test_roundtrip_net_class(tmp_path: Path):
    pcb_file = tmp_path / "test.kicad_pcb"
    pcb_file.write_text(MINIMAL_PCB)
    board = parse_pcb(pcb_file)
    add_net_class(board, "GND", clearance=0.3, trace_width=0.4)
    out = tmp_path / "out.kicad_pcb"
    write_pcb(board, out)
    text = out.read_text()
    assert 'net_class "GND"' in text
    assert "clearance 0.3" in text
    assert "trace_width 0.4" in text

    board2 = parse_pcb(out)
    nc = [n for n in board2.raw if isinstance(n, list) and n[0] == "net_class"][0]
    assert nc[1] == "GND"
