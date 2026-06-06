"""Tests for routing cost estimator."""

from ai_probe_router.models.board import Board, EdgeSegment, Footprint, Pad
from ai_probe_router.solvers.routing_cost import RoutingCost, estimate_routing_cost


def _make_board() -> Board:
    fp = Footprint(
        ref="U1", value="STM32", x=100, y=100,
        pads=[
            Pad(number="1", x=95, y=96.5, net_name="SWDIO", net_id=3),
            Pad(number="24", x=100, y=95, net_name="GND", net_id=1),
        ],
    )
    return Board(
        footprints=[fp],
        nets={"GND": 1, "SWDIO": 3},
        edges=[
            EdgeSegment(80, 80, 120, 80),
            EdgeSegment(120, 80, 120, 120),
            EdgeSegment(120, 120, 80, 120),
            EdgeSegment(80, 120, 80, 80),
        ],
    )


def test_cost_closer_is_cheaper():
    board = _make_board()
    target = [(95, 96.5)]
    cost_near = estimate_routing_cost(98, 96.5, target, board)
    cost_far = estimate_routing_cost(115, 96.5, target, board)
    assert cost_near.total < cost_far.total


def test_cost_no_targets():
    board = _make_board()
    cost = estimate_routing_cost(100, 100, [], board)
    assert cost.total == float("inf")


def test_cost_returns_dataclass():
    board = _make_board()
    cost = estimate_routing_cost(110, 110, [(95, 96.5)], board)
    assert isinstance(cost, RoutingCost)
    assert cost.distance > 0
    assert cost.total >= cost.distance


def test_congestion_increases_cost():
    fp1 = Footprint(ref="U1", x=100, y=100, pads=[
        Pad(number=str(i), x=100 + i * 0.5, y=100, net_name=f"N{i}") for i in range(10)
    ])
    board = Board(footprints=[fp1], nets={f"N{i}": i for i in range(10)})
    cost_congested = estimate_routing_cost(100, 100, [(100, 100)], board)
    board_empty = Board(footprints=[], nets={})
    cost_empty = estimate_routing_cost(100, 100, [(100, 100)], board_empty)
    assert cost_congested.congestion_penalty > cost_empty.congestion_penalty
