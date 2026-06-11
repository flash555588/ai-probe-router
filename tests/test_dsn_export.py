"""Tests for DSN export."""

from ai_probe_router.models.board import Board, EdgeSegment, Footprint, Pad
from ai_probe_router.routing.dsn_export import export_dsn


def _make_board() -> Board:
    fp = Footprint(
        ref="U1", value="MCU", lib_id="Package_QFP:LQFP-48_7x7mm_P0.5mm",
        x=10000, y=10000, layer="F.Cu",
        pads=[
            Pad(number="1", x=9996.5, y=9996.5, width=0.5, height=0.5,
                net_name="SWDIO", net_id=1, local_x=-3.5, local_y=-3.5),
            Pad(number="2", x=9997.0, y=9996.5, width=0.5, height=0.5,
                net_name="GND", net_id=2, local_x=-3.0, local_y=-3.5),
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

def test_dsn_custom_rules(tmp_path):
    board = _make_board()
    out = tmp_path / "test.dsn"
    export_dsn(board, out, trace_width_um=200, clearance_um=250)
    text = out.read_text(encoding="utf-8")
    assert "(rule (width 200))" in text
    assert "(rule (clearance 250))" in text


def test_dsn_no_board_outline(tmp_path):
    board = Board(raw=["kicad_pcb"], nets={}, footprints=[], edges=[])
    out = tmp_path / "test.dsn"
    export_dsn(board, out)
    text = out.read_text(encoding="utf-8")
    assert "(pcb" in text
    assert "(boundary" not in text


def test_dsn_library_pins_use_local_coordinates(tmp_path):
    board = _make_board()
    out = tmp_path / "test.dsn"
    export_dsn(board, out)
    text = out.read_text(encoding="utf-8")
    # library pins should be near -3500 um (local coord), not near 10,000,000 um (absolute)
    assert '(pin "1" -3500 -3500)' in text
    assert '(pin "2" -3000 -3500)' in text
