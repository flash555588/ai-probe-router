"""Tests for the allocated module graph wrapper."""

from __future__ import annotations

from ai_probe_router.models.dev_board import DevBoardPin, DevelopmentBoard
from ai_probe_router.models.probe import ProbeRequirement
from ai_probe_router.solvers.connector_allocator import allocate_connector_pins
from ai_probe_router.solvers.module_allocation_graph import (
    build_allocated_module_graph,
)
from ai_probe_router.solvers.pin_mapper import MappingResult, PinAssignment
from ai_probe_router.solvers.resource_allocator import ResourceAllocationResult


def _connector_result(assignments, pins, reqs):
    board = DevelopmentBoard(
        name="t", rows=1, pins_per_row=len(pins), pins=pins,
    )
    mapping = MappingResult(assignments=assignments)
    return allocate_connector_pins(mapping, board, reqs)


def test_empty_allocation_graph_ok():
    graph = build_allocated_module_graph(ResourceAllocationResult())
    assert graph.ok
    assert graph.connector_reservations == []


def test_connector_reservations_populated():
    pins = [
        DevBoardPin(name="P0", capabilities=["GPIO"]),
        DevBoardPin(name="P1", capabilities=["GPIO"]),
    ]
    reqs = [ProbeRequirement(net_name="LED", role="gpio")]
    connector = _connector_result(
        [PinAssignment(net_name="LED", pin_name="P0", pin_index=0)],
        pins, reqs,
    )
    alloc = ResourceAllocationResult(connector_result=connector)

    graph = build_allocated_module_graph(alloc)

    assert graph.ok
    assert len(graph.connector_reservations) == 2
    first = graph.connector_reservations[0]
    assert first["pin_name"] == "P0"
    assert first["status"] == "probe"
    assert first["net_name"] == "LED"
    assert graph.connector_reservations[1]["status"] == "free"


def test_connector_conflict_becomes_graph_error():
    pins = [DevBoardPin(name="P0", capabilities=["GPIO"])]
    reqs = [
        ProbeRequirement(net_name="A", role="gpio"),
        ProbeRequirement(net_name="B", role="gpio"),
    ]
    connector = _connector_result(
        [
            PinAssignment(net_name="A", pin_name="P0", pin_index=0),
            PinAssignment(net_name="B", pin_name="P0", pin_index=0),
        ],
        pins, reqs,
    )
    alloc = ResourceAllocationResult(connector_result=connector)

    graph = build_allocated_module_graph(alloc)

    assert not graph.ok
    assert any("CONNECTOR_PIN_CONFLICT" in e for e in graph.errors)


def test_connector_near_limit_becomes_graph_warning():
    pins = [
        DevBoardPin(name=f"P{i}", capabilities=["GPIO"]) for i in range(2)
    ]
    reqs = [
        ProbeRequirement(net_name="A", role="gpio"),
        ProbeRequirement(net_name="B", role="gpio"),
    ]
    connector = _connector_result(
        [
            PinAssignment(net_name="A", pin_name="P0", pin_index=0),
            PinAssignment(net_name="B", pin_name="P1", pin_index=1),
        ],
        pins, reqs,
    )
    alloc = ResourceAllocationResult(connector_result=connector)

    graph = build_allocated_module_graph(alloc)

    assert graph.ok
    assert "CONNECTOR_ALLOCATION_NEAR_LIMIT" in graph.warnings
