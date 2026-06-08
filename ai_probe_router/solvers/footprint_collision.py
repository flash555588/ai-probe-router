"""Footprint collision and bounds checking for module footprint preview."""

from __future__ import annotations

from dataclasses import dataclass

from ..models.board import Board
from ..models.footprint_preview import (
    FootprintPreviewIssue,
    FootprintPreviewSeverity,
    PlannedFootprint,
)


@dataclass
class CollisionBox:
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def intersects(self, other: CollisionBox) -> bool:
        return not (
            self.x_max <= other.x_min
            or self.x_min >= other.x_max
            or self.y_max <= other.y_min
            or self.y_min >= other.y_max
        )


def _box(fp: PlannedFootprint, size_mm: float = 5.0) -> CollisionBox:
    """Approximate collision box around footprint center."""
    half = size_mm / 2.0
    return CollisionBox(
        x_min=fp.x_mm - half,
        y_min=fp.y_mm - half,
        x_max=fp.x_mm + half,
        y_max=fp.y_mm + half,
    )


def check_footprint_collisions(
    planned: list[PlannedFootprint],
    existing_refs: set[str],
) -> list[FootprintPreviewIssue]:
    """Check collisions among planned footprints and against existing refs."""
    issues: list[FootprintPreviewIssue] = []
    boxes = [(fp, _box(fp)) for fp in planned]

    for i, (fp_a, box_a) in enumerate(boxes):
        # Collision with existing footprints by reference
        if fp_a.reference in existing_refs:
            issues.append(
                FootprintPreviewIssue(
                    severity=FootprintPreviewSeverity.ERROR,
                    code="FOOTPRINT_PREVIEW_COLLISION",
                    message=(
                        f"Reference {fp_a.reference} already exists on board"
                    ),
                    module_name=fp_a.module_name,
                    reference=fp_a.reference,
                )
            )
        # Collision with other planned footprints
        for j in range(i + 1, len(boxes)):
            fp_b, box_b = boxes[j]
            if box_a.intersects(box_b):
                issues.append(
                    FootprintPreviewIssue(
                        severity=FootprintPreviewSeverity.ERROR,
                        code="FOOTPRINT_PREVIEW_COLLISION",
                        message=(
                            f"Planned footprint {fp_a.reference} collides with "
                            f"{fp_b.reference}"
                        ),
                        module_name=fp_a.module_name,
                        reference=fp_a.reference,
                    )
                )
    return issues


def check_board_bounds(
    planned: list[PlannedFootprint],
    board: Board | None,
) -> list[FootprintPreviewIssue]:
    """Check that planned footprints fit inside the board outline."""
    issues: list[FootprintPreviewIssue] = []
    if board is None or not board.edges:
        return issues

    # Use bounding box of board edges as conservative check
    xs = [p[0] for edge in board.edges for p in edge]
    ys = [p[1] for edge in board.edges for p in edge]
    if not xs or not ys:
        return issues

    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    margin = 1.0  # 1mm margin

    for fp in planned:
        box = _box(fp)
        if box.x_min < x_min + margin or box.x_max > x_max - margin:
            issues.append(
                FootprintPreviewIssue(
                    severity=FootprintPreviewSeverity.ERROR,
                    code="FOOTPRINT_PREVIEW_OUT_OF_BOUNDS",
                    message=(
                        f"Footprint {fp.reference} x={fp.x_mm} outside "
                        f"board bounds [{x_min}, {x_max}]"
                    ),
                    module_name=fp.module_name,
                    reference=fp.reference,
                )
            )
        if box.y_min < y_min + margin or box.y_max > y_max - margin:
            issues.append(
                FootprintPreviewIssue(
                    severity=FootprintPreviewSeverity.ERROR,
                    code="FOOTPRINT_PREVIEW_OUT_OF_BOUNDS",
                    message=(
                        f"Footprint {fp.reference} y={fp.y_mm} outside "
                        f"board bounds [{y_min}, {y_max}]"
                    ),
                    module_name=fp.module_name,
                    reference=fp.reference,
                )
            )
    return issues


def check_keepout_violations(
    planned: list[PlannedFootprint],
    board: Board | None,
) -> list[FootprintPreviewIssue]:
    """Check planned footprints against board keepout zones."""
    issues: list[FootprintPreviewIssue] = []
    if board is None:
        return issues

    # Check against simple rectangular keepout zones if available
    keepouts = getattr(board, "keepout_zones", [])
    for fp in planned:
        box = _box(fp)
        for zone in keepouts:
            z_box = CollisionBox(
                x_min=zone.get("x_min", 0),
                y_min=zone.get("y_min", 0),
                x_max=zone.get("x_max", 0),
                y_max=zone.get("y_max", 0),
            )
            if box.intersects(z_box):
                issues.append(
                    FootprintPreviewIssue(
                        severity=FootprintPreviewSeverity.ERROR,
                        code="FOOTPRINT_PREVIEW_KEEPOUT_VIOLATION",
                        message=(
                            f"Footprint {fp.reference} violates keepout zone"
                        ),
                        module_name=fp.module_name,
                        reference=fp.reference,
                    )
                )
    return issues
