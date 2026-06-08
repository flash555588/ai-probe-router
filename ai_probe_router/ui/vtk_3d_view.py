"""3D VTK view for footprint preview overlay.

Renders a board plane and colored footprint bounding boxes.
VTK is imported lazily so the core package works without the optional
``plugin`` dependencies installed.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vtkmodules.vtkRenderingCore import (
        vtkActor,
        vtkRenderer,
        vtkRenderWindowInteractor,
    )

    from .footprint_overlay import FootprintOverlayItem
    from .report_loader import FootprintEntry, IssueEntry


def _require_vtk() -> SimpleNamespace:
    """Import VTK classes on demand."""
    try:
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
    except ImportError as exc:
        raise ImportError(
            "VTK is required for the 3D preview. "
            'Install with: pip install vtk or pip install -e ".[plugin]"'
        ) from exc

    return SimpleNamespace(
        VTK_HEXAHEDRON=VTK_HEXAHEDRON,
        vtkActor=vtkActor,
        vtkCellArray=vtkCellArray,
        vtkDataSetMapper=vtkDataSetMapper,
        vtkHexahedron=vtkHexahedron,
        vtkNamedColors=vtkNamedColors,
        vtkPlaneSource=vtkPlaneSource,
        vtkPoints=vtkPoints,
        vtkPolyDataMapper=vtkPolyDataMapper,
        vtkRenderer=vtkRenderer,
        vtkRenderWindow=vtkRenderWindow,
        vtkRenderWindowInteractor=vtkRenderWindowInteractor,
        vtkInteractorStyleTrackballCamera=vtkInteractorStyleTrackballCamera,
        vtkUnstructuredGrid=vtkUnstructuredGrid,
    )


def _create_board_plane(width: float = 100.0, height: float = 100.0) -> vtkActor:
    """Create a green semi-transparent board plane."""
    vtk = _require_vtk()
    plane = vtk.vtkPlaneSource()
    plane.SetOrigin(-width / 2, -height / 2, 0)
    plane.SetPoint1(width / 2, -height / 2, 0)
    plane.SetPoint2(-width / 2, height / 2, 0)
    plane.SetResolution(1, 1)

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(plane.GetOutputPort())

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    colors = vtk.vtkNamedColors()
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
    vtk = _require_vtk()
    half = size / 2.0
    points = vtk.vtkPoints()
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

    hexa = vtk.vtkHexahedron()
    for i in range(8):
        hexa.GetPointIds().SetId(i, i)

    cells = vtk.vtkCellArray()
    cells.InsertNextCell(hexa)

    grid = vtk.vtkUnstructuredGrid()
    grid.SetPoints(points)
    grid.SetCells(vtk.VTK_HEXAHEDRON, cells)

    mapper = vtk.vtkDataSetMapper()
    mapper.SetInputData(grid)

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    colors = vtk.vtkNamedColors()
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
    vtk = _require_vtk()
    renderer = vtk.vtkRenderer()
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
    vtk = _require_vtk()
    render_window = vtk.vtkRenderWindow()
    render_window.AddRenderer(renderer)
    render_window.SetSize(800, 600)
    render_window.SetWindowName("AI Probe Router 3D Preview")

    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(render_window)
    interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
    return interactor


# --------------------------------------------------------------------------- #
#  PR7.1 extended API
# --------------------------------------------------------------------------- #

class Vtk3DView:
    """VTK scene manager with footprint overlays and actor metadata.

    Integrates with FootprintOverlayBuilder and SeverityFilterState.
    """

    def __init__(self) -> None:
        vtk = _require_vtk()
        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.1, 0.1, 0.15)
        self._board_actor: vtkActor | None = None
        self._footprint_actors: list[vtkActor] = []
        self.actor_metadata: dict[int, dict[str, Any]] = {}
        self._selection_callback: Any | None = None

    def add_fallback_board(self, width: float = 100.0, height: float = 100.0) -> None:
        """Add a fallback board plane when STEP is unavailable."""
        if self._board_actor is not None:
            self.renderer.RemoveActor(self._board_actor)
        self._board_actor = _create_board_plane(width, height)
        self.renderer.AddActor(self._board_actor)

    def add_board_actor(self, actor: vtkActor) -> None:
        """Add an external board actor (e.g., from STEP)."""
        if self._board_actor is not None:
            self.renderer.RemoveActor(self._board_actor)
        self._board_actor = actor
        self.renderer.AddActor(actor)

    def add_footprint_overlays(
        self,
        items: list[FootprintOverlayItem],
    ) -> None:
        """Add colored footprint boxes from overlay items."""
        colors_map = {
            "error": "Tomato",
            "warning": "Gold",
            "info": "LimeGreen",
        }
        for item in items:
            color = colors_map.get(item.severity, "LimeGreen")
            actor = _create_box_actor(
                item.wx,
                item.wy,
                item.wz,
                size=item.width_mm,
                color_name=color,
            )
            self._footprint_actors.append(actor)
            self.renderer.AddActor(actor)
            # Store metadata keyed by actor id (hash)
            self.actor_metadata[id(actor)] = {
                "module_name": item.module_name,
                "reference": item.reference,
                "footprint": item.footprint,
                "severity": item.severity,
                "issue_codes": item.issue_codes,
            }

    def apply_visibility(self, visible_refs: set[str]) -> None:
        """Show/hide footprint actors by reference."""
        for actor in self._footprint_actors:
            meta = self.actor_metadata.get(id(actor), {})
            ref = meta.get("reference", "")
            actor.SetVisibility(ref in visible_refs)

    def reset_camera(self) -> None:
        """Reset camera to frame the scene."""
        self.renderer.ResetCamera()
        camera = self.renderer.GetActiveCamera()
        camera.SetViewUp(0, 1, 0)
        camera.Elevation(30)
        camera.Azimuth(30)
        self.renderer.ResetCameraClippingRange()

    def set_selection_callback(self, callback) -> None:
        """Set callback(module_name, reference) for actor selection."""
        self._selection_callback = callback

    def get_renderer(self) -> vtkRenderer:
        return self.renderer

    def clear_overlays(self) -> None:
        """Remove all footprint actors."""
        for actor in self._footprint_actors:
            self.renderer.RemoveActor(actor)
        self._footprint_actors.clear()
        self.actor_metadata.clear()

    def install_picker(self, interactor) -> None:
        """Install a prop picker on the interactor for click-to-inspect."""
        from vtkmodules.vtkRenderingCore import vtkPropPicker

        picker = vtkPropPicker()
        interactor.AddObserver(
            "LeftButtonPressEvent",
            lambda obj, event: self._on_pick(obj, event, picker),
        )

    def _on_pick(self, obj, event, picker) -> None:
        """Handle pick event: map actor to metadata and invoke callback."""
        interactor = obj
        click_pos = interactor.GetEventPosition()
        picker.Pick(click_pos[0], click_pos[1], 0, self.renderer)
        actor = picker.GetActor()
        if actor is None:
            return
        meta = self.actor_metadata.get(id(actor))
        if meta is None:
            return
        if self._selection_callback is not None:
            self._selection_callback(
                meta.get("module_name", ""),
                meta.get("reference", ""),
            )
