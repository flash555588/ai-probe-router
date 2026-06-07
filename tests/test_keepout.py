"""Tests for keepout zone generation."""

from ai_probe_router.eda_adapters.kicad.pcb_writer import add_keepout_zone
from ai_probe_router.models.board import Board


def _make_board() -> Board:
    return Board(raw=["kicad_pcb"], nets={}, footprints=[], edges=[])


def test_keepout_zone_structure():
    board = _make_board()
    add_keepout_zone(board, 10.0, 20.0, 3.0, 4.0)
    zones = [n for n in board.raw if isinstance(n, list) and n[0] == "zone"]
    assert len(zones) == 1
    zone = zones[0]
    assert ["net", "0"] in zone
    assert ["keepout",
            ["tracks", "allowed"],
            ["vias", "allowed"],
            ["pads", "allowed"],
            ["copperpour", "not_allowed"],
            ["footprints", "allowed"]] in zone


def test_keepout_can_disallow_items_explicitly():
    board = _make_board()
    add_keepout_zone(
        board,
        10.0,
        20.0,
        3.0,
        4.0,
        tracks_allowed=False,
        vias_allowed=False,
        pads_allowed=False,
        footprints_allowed=False,
    )
    zone = [n for n in board.raw if isinstance(n, list) and n[0] == "zone"][0]
    assert ["keepout",
            ["tracks", "not_allowed"],
            ["vias", "not_allowed"],
            ["pads", "not_allowed"],
            ["copperpour", "not_allowed"],
            ["footprints", "not_allowed"]] in zone


def test_keepout_polygon_corners():
    board = _make_board()
    add_keepout_zone(board, 10.0, 20.0, 4.0, 6.0)
    zone = [n for n in board.raw if n[0] == "zone"][0]
    polygon = [c for c in zone if isinstance(c, list) and c[0] == "polygon"][0]
    pts = [c for c in polygon if isinstance(c, list) and c[0] == "pts"][0]
    xy_points = [c for c in pts if c[0] == "xy"]
    assert len(xy_points) == 4
    # half_w=2, half_h=3
    assert ["xy", "8.0", "17.0"] in xy_points
    assert ["xy", "12.0", "17.0"] in xy_points
    assert ["xy", "12.0", "23.0"] in xy_points
    assert ["xy", "8.0", "23.0"] in xy_points


def test_keepout_layers():
    board = _make_board()
    add_keepout_zone(board, 0.0, 0.0, 2.0, 2.0, layers=["F.Cu"])
    zone = [n for n in board.raw if n[0] == "zone"][0]
    layers_node = [c for c in zone if c[0] == "layers"][0]
    assert "F.Cu" in layers_node[1:]
