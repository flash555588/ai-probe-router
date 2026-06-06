"""Tests for Board model extensions (BoundingBox, board_bounds, etc.)."""


from ai_probe_router.models.board import Board, BoundingBox, EdgeSegment, Footprint, Pad


def test_bounding_box_properties():
    bb = BoundingBox(10, 20, 50, 60)
    assert bb.width == 40
    assert bb.height == 40
    assert bb.center == (30, 40)


def test_bounding_box_contains():
    bb = BoundingBox(0, 0, 100, 100)
    assert bb.contains(50, 50)
    assert bb.contains(0, 0)
    assert bb.contains(100, 100)
    assert not bb.contains(-1, 50)
    assert not bb.contains(50, 101)


def test_bounding_box_inset():
    bb = BoundingBox(0, 0, 100, 100)
    inset = bb.inset(10)
    assert inset.min_x == 10
    assert inset.min_y == 10
    assert inset.max_x == 90
    assert inset.max_y == 90


def test_bounding_box_distance_inside():
    bb = BoundingBox(0, 0, 100, 100)
    assert bb.distance_to_edge(5, 50) == 5
    assert bb.distance_to_edge(50, 50) == 50


def test_bounding_box_distance_outside():
    bb = BoundingBox(0, 0, 100, 100)
    dist = bb.distance_to_edge(110, 50)
    assert abs(dist - 10) < 0.01


def test_board_bounds_from_edges():
    board = Board(edges=[
        EdgeSegment(80, 80, 120, 80),
        EdgeSegment(120, 80, 120, 120),
        EdgeSegment(120, 120, 80, 120),
        EdgeSegment(80, 120, 80, 80),
    ])
    bounds = board.board_bounds()
    assert bounds is not None
    assert bounds.min_x == 80
    assert bounds.min_y == 80
    assert bounds.max_x == 120
    assert bounds.max_y == 120
    assert bounds.width == 40
    assert bounds.height == 40


def test_board_bounds_none_when_no_edges():
    board = Board()
    assert board.board_bounds() is None


def test_footprint_bounds():
    fp = Footprint(ref="U1", x=100, y=100, pads=[
        Pad(number="1", x=95, y=96.5, width=1.2, height=0.5),
        Pad(number="2", x=105, y=103.5, width=1.2, height=0.5),
    ])
    board = Board(footprints=[fp])
    fb = board.footprint_bounds(fp)
    assert fb.min_x < 95
    assert fb.max_x > 105
    assert fb.min_y < 96.5
    assert fb.max_y > 103.5


def test_footprint_bounds_no_pads():
    fp = Footprint(ref="MH1", x=50, y=50)
    board = Board(footprints=[fp])
    fb = board.footprint_bounds(fp)
    assert fb.contains(50, 50)


def test_all_pad_positions():
    fp = Footprint(ref="U1", pads=[
        Pad(number="1", x=10, y=20, net_name="GND"),
        Pad(number="2", x=30, y=40, net_name="3V3"),
    ])
    board = Board(footprints=[fp])
    positions = board.all_pad_positions()
    assert len(positions) == 2
    assert positions[0] == (10, 20, "GND")
    assert positions[1] == (30, 40, "3V3")
