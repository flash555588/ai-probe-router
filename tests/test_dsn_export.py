"""Tests for DSN export."""

from ai_probe_router.models.board import Board, EdgeSegment, Footprint, Pad
from ai_probe_router.routing.dsn_export import export_dsn


def _make_board() -> Board:
    fp = Footprint(
        ref="U1", value="MCU", lib_id="Package_QFP:LQFP-48_7x7mm_P0.5mm",
        x=10000, y=10000, layer="F.Cu",
        pads=[
            Pad(number="1", x=-3.5, y=-3.5, width=0.5, height=0.5, net_name="SWDIO", net_id=1),
            Pad(number="2", x=-3.0, y=-3.5, width=0.5, height=0.5, net_name="GND", net_id=2),
        ],
    )
    return Board(
        raw=["kicad_pcb"],
        nets={"SWDIO": 1, "GND": 2},
        footprints=[fp],
        edges=[
            EdgeSegment(0, 0, 40, 0),
            EdgeSegment(40, 0, 40, 40),
            EdgeSegment(40, 40, 0, 40),
            EdgeSegment(0, 40, 0, 0),
        ],
    )


def test_dsn_export_basic(tmp_path):
    board = _make_board()
    out = tmp_path / "test.dsn"
    export_dsn(board, out)
    text = out.read_text(encoding="utf-8")
    assert "(pcb" in text
    assert "SWDIO" in text
    assert "GND" in text
    assert "U1-1" in text
    assert "U1-2" in text


def test_dsn_boundary_present(tmp_path):
    board = _make_board()
    out = tmp_path / "test.dsn"
    export_dsn(board, out)
    text = out.read_text(encoding="utf-8")
    assert "(boundary" in text
    assert "0 0" in text  # min_x, min_y in um


def test_dsn_layers_present(tmp_path):
    board = _make_board()
    out = tmp_path / "test.dsn"
    export_dsn(board, out)
    text = out.read_text(encoding="utf-8")
    assert "(layer TOP" in text
    assert "(layer BOTTOM" in text


def test_dsn_rules_present(tmp_path):
    board = _make_board()
    out = tmp_path / "test.dsn"
    export_dsn(board, out)
    text = out.read_text(encoding="utf-8")
    assert "(rule (width 150))" in text
    assert "(rule (clearance 150))" in text


def test_dsn_no_board_outline(tmp_path):
    board = Board(raw=["kicad_pcb"], nets={}, footprints=[], edges=[])
    out = tmp_path / "test.dsn"
    export_dsn(board, out)
    text = out.read_text(encoding="utf-8")
    assert "(pcb" in text
    assert "(boundary" not in text
