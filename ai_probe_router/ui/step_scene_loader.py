"""Optional STEP scene loading for the PR7 plugin shell.

This module does not import heavy CAD/VTK dependencies at module import time.
Import them lazily inside loader methods so the plugin shell still opens when
3D dependencies are unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class SceneLoadSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class SceneLoadIssue:
    severity: SceneLoadSeverity
    code: str
    message: str


@dataclass
class LoadedScene:
    ok: bool
    source_path: Path | None
    backend: str
    actor: Any | None = None
    issues: list[SceneLoadIssue] | None = None


class StepSceneLoader:
    """Load a STEP file or fall back to a synthetic board outline."""

    def load(self, step_path: Path | None) -> LoadedScene:
        if step_path is None:
            return LoadedScene(
                ok=False,
                source_path=None,
                backend="fallback",
                actor=None,
                issues=[
                    SceneLoadIssue(
                        SceneLoadSeverity.WARNING,
                        "STEP_FILE_NOT_CONFIGURED",
                        "No STEP file configured; using fallback board view.",
                    )
                ],
            )

        if not step_path.exists():
            return LoadedScene(
                ok=False,
                source_path=step_path,
                backend="fallback",
                actor=None,
                issues=[
                    SceneLoadIssue(
                        SceneLoadSeverity.WARNING,
                        "STEP_FILE_NOT_FOUND",
                        f"STEP file not found: {step_path}",
                    )
                ],
            )

        try:
            return self._load_with_vtk(step_path)
        except Exception as exc:  # noqa: BLE001
            return LoadedScene(
                ok=False,
                source_path=step_path,
                backend="fallback",
                actor=None,
                issues=[
                    SceneLoadIssue(
                        SceneLoadSeverity.WARNING,
                        "STEP_LOAD_FAILED",
                        f"Could not load STEP file; using fallback board view. "
                        f"Reason: {exc}",
                    )
                ],
            )

    def _load_with_vtk(self, step_path: Path) -> LoadedScene:
        """Attempt to load STEP via VTK. Falls back if unavailable."""
        try:
            from vtkmodules.vtkIOGeometry import vtkSTLReader
            from vtkmodules.vtkRenderingCore import (
                vtkActor,
                vtkPolyDataMapper,
            )
        except ImportError as exc:
            raise RuntimeError(f"VTK not available: {exc}") from exc

        # VTK does not have a built-in STEP reader in most builds.
        # Try to load as STL first (in case user converted STEP→STL).
        reader = vtkSTLReader()
        reader.SetFileName(str(step_path))
        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(reader.GetOutputPort())
        actor = vtkActor()
        actor.SetMapper(mapper)
        return LoadedScene(
            ok=True,
            source_path=step_path,
            backend="vtk-stl",
            actor=actor,
            issues=[],
        )

    def build_fallback_board(
        self,
        width_mm: float = 100.0,
        height_mm: float = 100.0,
        thickness_mm: float = 1.6,
    ) -> LoadedScene:
        """Build a synthetic extruded board actor without external files."""
        try:
            from vtkmodules.vtkCommonCore import vtkPoints
            from vtkmodules.vtkCommonDataModel import (
                VTK_HEXAHEDRON,
                vtkCellArray,
                vtkHexahedron,
                vtkUnstructuredGrid,
            )
            from vtkmodules.vtkRenderingCore import (
                vtkActor,
                vtkDataSetMapper,
            )
        except ImportError as exc:
            raise RuntimeError(f"VTK not available: {exc}") from exc

        hw = width_mm / 2.0
        hh = height_mm / 2.0
        ht = thickness_mm / 2.0

        pts = vtkPoints()
        coords = [
            (-hw, -hh, -ht), (hw, -hh, -ht),
            (hw, hh, -ht), (-hw, hh, -ht),
            (-hw, -hh, ht), (hw, -hh, ht),
            (hw, hh, ht), (-hw, hh, ht),
        ]
        for x, y, z in coords:
            pts.InsertNextPoint(x, y, z)

        hexa = vtkHexahedron()
        for i in range(8):
            hexa.GetPointIds().SetId(i, i)

        cells = vtkCellArray()
        cells.InsertNextCell(hexa)

        grid = vtkUnstructuredGrid()
        grid.SetPoints(pts)
        grid.SetCells(VTK_HEXAHEDRON, cells)

        mapper = vtkDataSetMapper()
        mapper.SetInputData(grid)

        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(0.2, 0.6, 0.3)
        actor.GetProperty().SetOpacity(0.5)

        return LoadedScene(
            ok=True,
            source_path=None,
            backend="fallback-board",
            actor=actor,
            issues=[],
        )
