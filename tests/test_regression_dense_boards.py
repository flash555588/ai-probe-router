"""Regression fixtures for dense board routing and containment cases."""

from ai_probe_router.eda_adapters.kicad.pcb_writer import add_track_segment
from ai_probe_router.models.board import Board, EdgeSegment, Footprint, Pad
from ai_probe_router.solvers.grid_router import route_grid


def test_grid_router_escapes_fine_pitch_ic_and_dense_connector():
    board = Board(
        nets={"SIG": 1, "BLOCK": 2},
        edges=[
            EdgeSegment(0, 0, 40, 0),
            EdgeSegment(40, 0, 40, 30),
            EdgeSegment(40, 30, 0, 30),
            EdgeSegment(0, 30, 0, 0),
        ],
    )
    fine_pitch_pads = [
        Pad(
            number=str(i + 1),
            x=6.0,
            y=10.0 + i * 0.5,
            width=1.2,
            height=0.28,
            net_name="SIG" if i == 10 else f"U_NET_{i}",
            net_id=1 if i == 10 else 10 + i,
            layers=["F.Cu", "F.Mask"],
        )
        for i in range(20)
    ]
    connector_pads = [
        Pad(
            number=str(i + 1),
            x=34.0,
            y=7.0 + i * 0.8,
            width=0.4,
            height=0.4,
            net_name="SIG" if i == 10 else f"J_NET_{i}",
            net_id=1 if i == 10 else 100 + i,
            layers=["F.Cu", "F.Mask"],
        )
        for i in range(20)
    ]
    board.footprints.extend([
        Footprint(ref="U_FINE", pads=fine_pitch_pads),
        Footprint(ref="J_DENSE", pads=connector_pads),
    ])
    add_track_segment(board, "BLOCK", 20.0, 4.0, 20.0, 26.0, width=0.4)

    result = route_grid(
        board, "SIG", (6.0, 15.0), (34.0, 15.0),
        width=0.2, clearance=0.2, grid=0.5,
    )

    assert result.ok
    assert len(result.points) > 2
    blocker = ((20.0, 4.0), (20.0, 26.0))
    for start, end in zip(result.points, result.points[1:]):
        assert not _segments_intersect(start, end, blocker[0], blocker[1])


def test_grid_router_keeps_route_out_of_board_cutout():
    board = Board(
        nets={"SIG": 1},
        edges=[
            EdgeSegment(0, 0, 40, 0),
            EdgeSegment(40, 0, 40, 30),
            EdgeSegment(40, 30, 0, 30),
            EdgeSegment(0, 30, 0, 0),
            EdgeSegment(14, 10, 26, 10),
            EdgeSegment(26, 10, 26, 20),
            EdgeSegment(26, 20, 14, 20),
            EdgeSegment(14, 20, 14, 10),
        ],
    )
    result = route_grid(
        board, "SIG", (8.0, 15.0), (32.0, 15.0),
        width=0.2, clearance=0.2, grid=0.5,
    )

    assert result.ok
    cutout_edges = [
        ((14.0, 10.0), (26.0, 10.0)),
        ((26.0, 10.0), (26.0, 20.0)),
        ((26.0, 20.0), (14.0, 20.0)),
        ((14.0, 20.0), (14.0, 10.0)),
    ]
    for start, end in zip(result.points, result.points[1:]):
        assert all(
            not _segments_intersect(start, end, edge_start, edge_end)
            for edge_start, edge_end in cutout_edges
        )


def test_grid_router_reports_route_quality_metrics():
    board = Board(
        nets={"SIG": 1, "BLOCK": 2},
        edges=[
            EdgeSegment(0, 0, 20, 0),
            EdgeSegment(20, 0, 20, 12),
            EdgeSegment(20, 12, 0, 12),
            EdgeSegment(0, 12, 0, 0),
        ],
        raw=["kicad_pcb"],
    )
    add_track_segment(board, "BLOCK", 10.0, 0.0, 10.0, 8.0, width=0.4)

    result = route_grid(
        board, "SIG", (2.0, 4.0), (18.0, 4.0),
        width=0.2, clearance=0.2, grid=1.0,
    )

    assert result.ok
    assert result.length_mm > 16.0
    assert result.bend_count > 0


def test_grid_router_penalizes_unnecessary_meanders():
    board = Board(
        nets={"SIG": 1, "BLOCK": 2},
        edges=[
            EdgeSegment(0, 0, 20, 0),
            EdgeSegment(20, 0, 20, 20),
            EdgeSegment(20, 20, 0, 20),
            EdgeSegment(0, 20, 0, 0),
        ],
        raw=["kicad_pcb"],
    )
    add_track_segment(board, "BLOCK", 9.0, 9.0, 11.0, 11.0, width=0.4)

    result = route_grid(
        board, "SIG", (2.0, 2.0), (18.0, 18.0),
        width=0.2, clearance=0.2, grid=1.0, bend_penalty=4.0,
    )

    assert result.ok
    assert result.bend_count == 1
    assert len(result.points) == 3


def _segments_intersect(
    a1: tuple[float, float],
    a2: tuple[float, float],
    b1: tuple[float, float],
    b2: tuple[float, float],
) -> bool:
    def orient(
        p: tuple[float, float],
        q: tuple[float, float],
        r: tuple[float, float],
    ) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def on_segment(
        p: tuple[float, float],
        q: tuple[float, float],
        r: tuple[float, float],
    ) -> bool:
        return (
            min(p[0], r[0]) <= q[0] <= max(p[0], r[0])
            and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])
        )

    o1 = orient(a1, a2, b1)
    o2 = orient(a1, a2, b2)
    o3 = orient(b1, b2, a1)
    o4 = orient(b1, b2, a2)
    eps = 1e-9
    if o1 * o2 < 0 and o3 * o4 < 0:
        return True
    if abs(o1) <= eps and on_segment(a1, b1, a2):
        return True
    if abs(o2) <= eps and on_segment(a1, b2, a2):
        return True
    if abs(o3) <= eps and on_segment(b1, a1, b2):
        return True
    if abs(o4) <= eps and on_segment(b1, a2, b2):
        return True
    return False
