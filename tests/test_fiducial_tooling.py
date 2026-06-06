"""Tests for fiducial and tooling hole placement."""

from ai_probe_router.eda_adapters.kicad.pcb_writer import (
    add_fiducial_footprint,
    add_tooling_hole_footprint,
)
from ai_probe_router.models.board import Board


def _make_board() -> Board:
    return Board(
        raw=["kicad_pcb", ["version", "20240108"]],
        nets={},
        footprints=[],
        edges=[],
    )


def test_fiducial_footprint():
    board = _make_board()
    add_fiducial_footprint(board, 10.0, 20.0, ref="FID1")
    fps = [n for n in board.raw if isinstance(n, list) and n[0] == "footprint"]
    assert len(fps) == 1
    fp = fps[0]
    assert "Fiducial" in fp[1]
    assert ["at", "10.0", "20.0"] in fp


def test_fiducial_smd_pad():
    board = _make_board()
    add_fiducial_footprint(board, 5.0, 5.0, ref="FID2", diameter_mm=1.5)
    fp = [n for n in board.raw if n[0] == "footprint"][0]
    pads = [c for c in fp if isinstance(c, list) and c[0] == "pad"]
    assert len(pads) == 1
    assert pads[0][3] == "circle"


def test_tooling_hole_footprint():
    board = _make_board()
    add_tooling_hole_footprint(board, 30.0, 40.0, ref="TH1")
    fps = [n for n in board.raw if isinstance(n, list) and n[0] == "footprint"]
    assert len(fps) == 1
    fp = fps[0]
    assert "MountingHole" in fp[1]
    assert ["at", "30.0", "40.0"] in fp


def test_tooling_hole_np_thru_hole():
    board = _make_board()
    add_tooling_hole_footprint(board, 0.0, 0.0, ref="TH2", drill_mm=3.2)
    fp = [n for n in board.raw if n[0] == "footprint"][0]
    pads = [c for c in fp if isinstance(c, list) and c[0] == "pad"]
    assert len(pads) == 1
    assert pads[0][2] == "np_thru_hole"
    drill_node = [c for c in pads[0] if isinstance(c, list) and c[0] == "drill"]
    assert drill_node[0][1] == "3.2"


def test_fiducial_reference_property():
    board = _make_board()
    add_fiducial_footprint(board, 1.0, 1.0, ref="FID3")
    fp = [n for n in board.raw if n[0] == "footprint"][0]
    props = [c for c in fp if isinstance(c, list) and c[0] == "property"]
    refs = [p for p in props if p[1] == "Reference"]
    assert len(refs) == 1
    assert refs[0][2] == "FID3"


def test_tooling_hole_reference_property():
    board = _make_board()
    add_tooling_hole_footprint(board, 1.0, 1.0, ref="TH3")
    fp = [n for n in board.raw if n[0] == "footprint"][0]
    props = [c for c in fp if isinstance(c, list) and c[0] == "property"]
    refs = [p for p in props if p[1] == "Reference"]
    assert len(refs) == 1
    assert refs[0][2] == "TH3"
