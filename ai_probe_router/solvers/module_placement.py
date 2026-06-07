"""Hierarchical module placement planner.

This creates a deterministic placement scaffold for selected modules. It does
not emit real footprints; it produces regions and component coordinates for
reports and future synthesis.
"""

from __future__ import annotations

import math

from ..models.board import Board, BoundingBox
from ..models.module import ComponentSpec
from ..models.module_graph import ModuleGraph, ModuleInstance
from ..models.module_placement import (
    ComponentPlacement,
    ModulePlacementResult,
    ModuleRegionPlan,
)


def plan_module_placement(
    graph: ModuleGraph,
    board: Board | None,
) -> ModulePlacementResult:
    result = ModulePlacementResult()
    if board is None:
        result.skipped = True
        result.skip_reason = "no_board"
        return result

    bounds = board.board_bounds()
    if bounds is None:
        result.skipped = True
        result.skip_reason = "no_board_outline"
        return result

    occupied: list[BoundingBox] = []
    for index, instance in enumerate(graph.instances):
        region, anchor = _assign_region(instance, bounds, occupied, index)
        instance.region = region
        occupied.append(region)
        region_plan = ModuleRegionPlan(
            module_id=instance.instance_id,
            module_name=instance.name,
            module_type=instance.module_type,
            region=region,
            anchor=anchor,
            probe_zone=_probe_zone(region),
            connector_zone=_connector_zone(region),
        )
        result.plan.regions.append(region_plan)
        result.plan.components.extend(_place_components(instance, region))

    _warn_overlaps(result)
    return result


def _assign_region(
    instance: ModuleInstance,
    board_bounds: BoundingBox,
    occupied: list[BoundingBox],
    index: int,
) -> tuple[BoundingBox, str]:
    anchor = _anchor_for(instance)
    center = _anchor_center(anchor, board_bounds, index)
    side = max(math.sqrt(max(instance.area_mm2, 25.0)) * 1.25, 6.0)
    width = min(side, board_bounds.width * 0.45)
    height = min(side, board_bounds.height * 0.45)

    region = _region_around(center, width, height, board_bounds)
    if not _overlaps_any(region, occupied):
        return region, anchor

    step = max(width, height) * 0.65
    for radius in range(1, 6):
        for dx, dy in (
            (radius * step, 0.0),
            (-radius * step, 0.0),
            (0.0, radius * step),
            (0.0, -radius * step),
            (radius * step, radius * step),
            (-radius * step, radius * step),
            (radius * step, -radius * step),
            (-radius * step, -radius * step),
        ):
            candidate = _region_around(
                (center[0] + dx, center[1] + dy),
                width,
                height,
                board_bounds,
            )
            if not _overlaps_any(candidate, occupied):
                return candidate, anchor
    return region, anchor


def _anchor_for(instance: ModuleInstance) -> str:
    if instance.preferred_region:
        return instance.preferred_region
    module_type = instance.module_type.lower()
    if "power" in module_type or instance.rails:
        return "power_input"
    if "debug" in module_type:
        return "probe_edge"
    if "analog" in module_type:
        return "top"
    if any(token in module_type for token in ("communication", "rs485", "can")):
        return "right"
    return "center"


def _anchor_center(
    anchor: str,
    bounds: BoundingBox,
    index: int,
) -> tuple[float, float]:
    anchor = anchor.lower()
    mapping = {
        "left": (0.22, 0.50),
        "right": (0.78, 0.50),
        "top": (0.50, 0.22),
        "bottom": (0.50, 0.78),
        "center": (0.50, 0.50),
        "power_input": (0.18, 0.50),
        "probe_edge": (0.50, 0.82),
    }
    fx, fy = mapping.get(anchor, mapping["center"])
    jitter = ((index % 3) - 1) * 0.06
    return (
        bounds.min_x + bounds.width * min(max(fx + jitter, 0.12), 0.88),
        bounds.min_y + bounds.height * min(max(fy, 0.12), 0.88),
    )


def _region_around(
    center: tuple[float, float],
    width: float,
    height: float,
    bounds: BoundingBox,
) -> BoundingBox:
    half_w = width / 2
    half_h = height / 2
    cx = min(max(center[0], bounds.min_x + half_w), bounds.max_x - half_w)
    cy = min(max(center[1], bounds.min_y + half_h), bounds.max_y - half_h)
    return BoundingBox(cx - half_w, cy - half_h, cx + half_w, cy + half_h)


def _overlaps_any(region: BoundingBox, occupied: list[BoundingBox]) -> bool:
    return any(_overlaps(region, other) for other in occupied)


def _overlaps(a: BoundingBox, b: BoundingBox) -> bool:
    return not (
        a.max_x <= b.min_x
        or a.min_x >= b.max_x
        or a.max_y <= b.min_y
        or a.min_y >= b.max_y
    )


def _probe_zone(region: BoundingBox) -> BoundingBox:
    height = min(region.height * 0.20, 3.0)
    return BoundingBox(region.min_x, region.max_y - height, region.max_x, region.max_y)


def _connector_zone(region: BoundingBox) -> BoundingBox:
    width = min(region.width * 0.22, 4.0)
    return BoundingBox(region.max_x - width, region.min_y, region.max_x, region.max_y)


def _place_components(
    instance: ModuleInstance,
    region: BoundingBox,
) -> list[ComponentPlacement]:
    placements: list[ComponentPlacement] = []
    core_ref = ""
    lanes = {
        "core": _spiral_positions(region.center, region.width * 0.16),
        "passive": _edge_positions(region, "top"),
        "protection": _edge_positions(region, "bottom"),
        "io": _edge_positions(region, "right"),
    }
    lane_indices = {"core": 0, "passive": 0, "protection": 0, "io": 0}

    for component in instance.components:
        refs = instance.refdes_pools.get(component.type, [])
        for item_index in range(component.count):
            refdes = refs[item_index] if item_index < len(refs) else "U?"
            placement_class = _placement_class(component)
            points = lanes[placement_class]
            point_index = lane_indices[placement_class] % len(points)
            x, y = points[point_index]
            lane_indices[placement_class] += 1
            near_ref = core_ref if placement_class in {"passive", "protection"} else ""
            if placement_class == "core" and not core_ref:
                core_ref = refdes
            placements.append(
                ComponentPlacement(
                    module_id=instance.instance_id,
                    refdes=refdes,
                    component_type=component.type,
                    role=component.role,
                    x=x,
                    y=y,
                    placement_class=placement_class,
                    near_refdes=near_ref,
                )
            )
    return placements


def _placement_class(component: ComponentSpec) -> str:
    core = {
        "adc",
        "analog_mux",
        "current_monitor",
        "eeprom",
        "gpio_expander",
        "level_shifter",
        "mcu_gpio",
        "rs485_transceiver",
    }
    protection = {
        "common_mode_choke",
        "esd_array",
        "fuse",
        "rc_filter",
        "resistor_array",
        "series_resistor",
        "tvs_diode",
    }
    io = {"connector", "testpad"}
    if component.type in core:
        return "core"
    if component.type in protection:
        return "protection"
    if component.type in io:
        return "io"
    return "passive"


def _spiral_positions(
    center: tuple[float, float],
    step: float,
) -> list[tuple[float, float]]:
    cx, cy = center
    step = max(step, 1.0)
    return [
        (cx, cy),
        (cx + step, cy),
        (cx, cy + step),
        (cx - step, cy),
        (cx, cy - step),
        (cx + step, cy + step),
        (cx - step, cy - step),
    ]


def _edge_positions(region: BoundingBox, edge: str) -> list[tuple[float, float]]:
    count = 16
    margin_x = max(region.width * 0.12, 1.0)
    margin_y = max(region.height * 0.12, 1.0)
    points: list[tuple[float, float]] = []
    for index in range(count):
        t = (index + 1) / (count + 1)
        if edge == "top":
            points.append((
                region.min_x + margin_x + t * max(region.width - margin_x * 2, 0.1),
                region.min_y + margin_y,
            ))
        elif edge == "bottom":
            points.append((
                region.min_x + margin_x + t * max(region.width - margin_x * 2, 0.1),
                region.max_y - margin_y,
            ))
        else:
            points.append((
                region.max_x - margin_x,
                region.min_y + margin_y + t * max(region.height - margin_y * 2, 0.1),
            ))
    return points


def _warn_overlaps(result: ModulePlacementResult) -> None:
    regions = result.plan.regions
    for i, left in enumerate(regions):
        for right in regions[i + 1:]:
            if _overlaps(left.region, right.region):
                result.warnings.append(
                    f"{left.module_id} region overlaps {right.module_id}"
                )

