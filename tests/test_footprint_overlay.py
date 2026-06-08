"""Tests for footprint overlay builder."""

from ai_probe_router.models.footprint_preview import (
    FootprintPreviewIssue,
    FootprintPreviewResult,
    FootprintPreviewSeverity,
    PlannedFootprint,
)
from ai_probe_router.ui.coordinate_transform import fit_frame_to_board
from ai_probe_router.ui.footprint_overlay import (
    FootprintOverlayBuilder,
    OverlaySeverity,
)


def test_build_items_from_empty_data():
    frame = fit_frame_to_board(100.0, 100.0)
    builder = FootprintOverlayBuilder(frame)
    items = builder.build_items(None)
    assert items == []


def test_build_items_with_severity():
    frame = fit_frame_to_board(100.0, 100.0)
    result = FootprintPreviewResult(
        planned_footprints=[
            PlannedFootprint(
                module_name="mod_a",
                reference="U1",
                footprint="fp",
                x_mm=10.0,
                y_mm=20.0,
                rotation_deg=0.0,
                side="top",
                role="mcu",
            )
        ],
        issues=[
            FootprintPreviewIssue(
                severity=FootprintPreviewSeverity.ERROR,
                code="COLLISION",
                message="collision",
                module_name="mod_a",
                reference="U1",
            )
        ],
    )
    builder = FootprintOverlayBuilder(frame)
    items = builder.build_items(result)
    assert len(items) == 1
    assert items[0].reference == "U1"
    assert items[0].severity == OverlaySeverity.ERROR
    assert "COLLISION" in items[0].issue_codes


def test_build_items_warning_over_info():
    frame = fit_frame_to_board(100.0, 100.0)
    result = FootprintPreviewResult(
        planned_footprints=[
            PlannedFootprint(
                module_name="mod_a",
                reference="U1",
                footprint="fp",
                x_mm=10.0,
                y_mm=20.0,
                rotation_deg=0.0,
                side="top",
            )
        ],
        issues=[
            FootprintPreviewIssue(
                severity=FootprintPreviewSeverity.WARNING,
                code="DENSE",
                message="dense",
                module_name="mod_a",
                reference="U1",
            ),
            FootprintPreviewIssue(
                severity=FootprintPreviewSeverity.INFO,
                code="INFO",
                message="info",
                module_name="mod_a",
                reference="U1",
            ),
        ],
    )
    builder = FootprintOverlayBuilder(frame)
    items = builder.build_items(result)
    assert items[0].severity == OverlaySeverity.WARNING


def test_build_items_maps_world_coordinates():
    frame = fit_frame_to_board(100.0, 100.0)
    result = FootprintPreviewResult(
        planned_footprints=[
            PlannedFootprint(
                module_name="mod_a",
                reference="U1",
                footprint="fp",
                x_mm=50.0,
                y_mm=50.0,
                rotation_deg=0.0,
                side="top",
            )
        ],
        issues=[],
    )
    builder = FootprintOverlayBuilder(frame)
    items = builder.build_items(result)
    assert items[0].wx == 0.0  # centered at origin
    assert items[0].wy == 0.0
    assert items[0].wz == frame.top_z
