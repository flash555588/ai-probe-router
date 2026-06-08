"""3D VTK view for footprint preview overlay.

Renders a board plane and colored footprint bounding boxes.
Requires vtk and PyQt6.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import vtkmodules.vtkRenderingOpenGL2  # noqa: F401  ensure OpenGL backend
from vtkmodules.vtkCommonColor import vtkNamedColors
from vtkmodules.vtkCommonCore import vtkPoints
from vtkmodules.vtkCommonDataModel import (
    VTK_HEXAHEDRON,
    vtkCellArray,
    vtkHexahedron,
    vtkUnstructuredGrid,
)
from vtkmodules.vtkFiltersSources import vtkPlaneSource
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
from vtkmodules.vtkRenderingCore import (
    vtkActor,
    vtkDataSetMapper,
    vtkPolyDataMapper,
    vtkRenderer,
    vtkRenderWindow,
    vtkRenderWindowInteractor,
)

if TYPE_CHECKING:
    from .report_loader import FootprintEntry, IssueEntry


def _create_board_plane(width: float = 100.0, height: float = 100.0) -> vtkActor:
    """Create a green semi-transparent board plane."""
    plane = vtkPlaneSource()
    plane.SetOrigin(-width / 2, -height / 2, 0)
    plane.SetPoint1(width / 2, -height / 2, 0)
    plane.SetPoint2(-width / 2, height / 2, 0)
    plane.SetResolution(1, 1)

    mapper = vtkPolyDataMapper()
    mapper.SetInputConnection(plane.GetOutputPort())

    actor = vtkActor()
    actor.SetMapper(mapper)
    colors = vtkNamedColors()
    actor.GetProperty().SetColor(colors.GetColor3d("SeaGreen"))
    actor.GetProperty().SetOpacity(0.4)
    return actor


def _create_box_actor(
    cx: float,
    cy: float,
    cz: float,
    size: float = 5.0,
    color_name: str = "Gold",
) -> vtkActor:
    """Create a simple hexahedron (box) actor at (cx, cy, cz)."""
    half = size / 2.0
    points = vtkPoints()
    coords = [
        (cx - half, cy - half, cz - half),
        (cx + half, cy - half, cz - half),
        (cx + half, cy + half, cz - half),
        (cx - half, cy + half, cz - half),
        (cx - half, cy - half, cz + half),
        (cx + half, cy - half, cz + half),
        (cx + half, cy + half, cz + half),
        (cx - half, cy + half, cz + half),
    ]
    for x, y, z in coords:
        points.InsertNextPoint(x, y, z)

    hexa = vtkHexahedron()
    for i in range(8):
        hexa.GetPointIds().SetId(i, i)

    cells = vtkCellArray()
    cells.InsertNextCell(hexa)

    grid = vtkUnstructuredGrid()
    grid.SetPoints(points)
    grid.SetCells(VTK_HEXAHEDRON, cells)

    mapper = vtkDataSetMapper()
    mapper.SetInputData(grid)

    actor = vtkActor()
    actor.SetMapper(mapper)
    colors = vtkNamedColors()
    actor.GetProperty().SetColor(colors.GetColor3d(color_name))
    actor.GetProperty().SetOpacity(0.8)
    return actor


def build_3d_scene(
    footprints: list[FootprintEntry],
    issues: list[IssueEntry],
    board_width: float = 100.0,
    board_height: float = 100.0,
) -> vtkRenderer:
    """Build a VTK renderer with board plane and footprint boxes."""
    renderer = vtkRenderer()
    renderer.SetBackground(0.1, 0.1, 0.15)

    # Board plane
    board_actor = _create_board_plane(board_width, board_height)
    renderer.AddActor(board_actor)

    # Build issue lookup by reference
    issue_by_ref: dict[str, str] = {}
    for issue in issues:
        ref = issue.reference or ""
        if ref and issue.severity in ("error", "warning"):
            # error takes precedence over warning
            if ref not in issue_by_ref or issue.severity == "error":
                issue_by_ref[ref] = issue.severity

    colors_map = {
        "error": "Tomato",
        "warning": "Gold",
    }

    for fp in footprints:
        severity = issue_by_ref.get(fp.reference, "")
        color = colors_map.get(severity, "LimeGreen")
        # Offset z by side: top = +1mm, bottom = -1mm
        z = 1.0 if fp.side == "top" else -1.0
        actor = _create_box_actor(fp.x_mm, fp.y_mm, z, size=4.0, color_name=color)
        renderer.AddActor(actor)

    # Fit camera to board
    renderer.ResetCamera()
    camera = renderer.GetActiveCamera()
    camera.SetViewUp(0, 1, 0)
    camera.Elevation(30)
    camera.Azimuth(30)
    renderer.ResetCameraClippingRange()

    return renderer


def create_vtk_interactor(
    renderer: vtkRenderer,
) -> vtkRenderWindowInteractor:
    """Create a standalone VTK interactor (for testing without Qt)."""
    render_window = vtkRenderWindow()
    render_window.AddRenderer(renderer)
    render_window.SetSize(800, 600)
    render_window.SetWindowName("AI Probe Router 3D Preview")

    interactor = vtkRenderWindowInteractor()
    interactor.SetRenderWindow(render_window)
    interactor.SetInteractorStyle(vtkInteractorStyleTrackballCamera())
    return interactor
