"""Tests for SES import."""

from ai_probe_router.models.board import Board
from ai_probe_router.routing.ses_import import import_ses


def _make_board() -> Board:
    return Board(raw=["kicad_pcb"], nets={}, footprints=[], edges=[])


def test_ses_import_wire(tmp_path):
    board = _make_board()
    ses = '''(session "test"
  (base_design "test")
  (route
    (net "GND"
      (wire (path TOP 150 10000 10000 20000 10000))
    )
  )
)'''
    path = tmp_path / "test.ses"
    path.write_text(ses, encoding="utf-8")
    import_ses(board, path)
    segs = [n for n in board.raw if isinstance(n, list) and n[0] == "segment"]
    assert len(segs) == 1
    seg = segs[0]
    assert ["start", "10.0", "10.0"] in seg
    assert ["end", "20.0", "10.0"] in seg


def test_ses_import_no_file(tmp_path):
    board = _make_board()
    path = tmp_path / "empty.ses"
    path.write_text('(session "empty" (base_design "empty") (route))', encoding="utf-8")
    import_ses(board, path)
    segs = [n for n in board.raw if isinstance(n, list) and n[0] == "segment"]
    assert len(segs) == 0


def test_ses_import_layer_mapping(tmp_path):
    board = _make_board()
    ses = '''(session "test"
  (route
    (net "SIG"
      (wire (path BOTTOM 200 5000 5000 15000 5000))
    )
  )
)'''
    path = tmp_path / "test.ses"
    path.write_text(ses, encoding="utf-8")
    import_ses(board, path)
    seg = [n for n in board.raw if n[0] == "segment"][0]
    layer_node = [c for c in seg if c[0] == "layer"][0]
    assert layer_node[1] == "B.Cu"


def test_ses_import_multi_path_wire(tmp_path):
    board = _make_board()
    ses = '''(session "test"
  (route
    (net "SIG"
      (wire
        (path TOP 150 0 0 10000 0)
        (path TOP 150 10000 0 20000 0)
      )
    )
  )
)'''
    path = tmp_path / "test.ses"
    path.write_text(ses, encoding="utf-8")
    import_ses(board, path)
    segs = [n for n in board.raw if isinstance(n, list) and n[0] == "segment"]
    assert len(segs) == 2


def test_ses_import_via_reordered_attrs(tmp_path):
    board = _make_board()
    ses = '''(session "test"
  (route
    (net "SIG"
      (via (via_via TOP BOTTOM) (xy 30000 40000))
    )
  )
)'''
    path = tmp_path / "test.ses"
    path.write_text(ses, encoding="utf-8")
    import_ses(board, path)
    vias = [n for n in board.raw if isinstance(n, list) and n[0] == "via"]
    assert len(vias) == 1
    at = [c for c in vias[0] if c[0] == "at"][0]
    assert at[1] == "30.0"
    assert at[2] == "40.0"
    layers = [c for c in vias[0] if c[0] == "layers"][0]
    assert "F.Cu" in layers
    assert "B.Cu" in layers
