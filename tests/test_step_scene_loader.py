"""Tests for STEP scene loader with fallback rendering."""

import importlib.util
from pathlib import Path

import pytest

from ai_probe_router.ui.step_scene_loader import (
    LoadedScene,
    SceneLoadIssue,
    SceneLoadSeverity,
    StepSceneLoader,
)


class TestStepSceneLoader:
    def test_none_path_returns_fallback(self):
        loader = StepSceneLoader()
        scene = loader.load(None)
        assert not scene.ok
        assert scene.backend == "fallback"
        assert scene.actor is None
        assert any(i.code == "STEP_FILE_NOT_CONFIGURED" for i in scene.issues)

    def test_missing_file_returns_fallback(self, tmp_path):
        loader = StepSceneLoader()
        scene = loader.load(tmp_path / "missing.step")
        assert not scene.ok
        assert scene.backend == "fallback"
        assert any(i.code == "STEP_FILE_NOT_FOUND" for i in scene.issues)

    @pytest.mark.skipif(importlib.util.find_spec("vtkmodules") is None, reason="vtk not installed")
    def test_fallback_board_builds_actor(self):
        loader = StepSceneLoader()
        scene = loader.build_fallback_board(100.0, 80.0, 1.6)
        assert scene.ok
        assert scene.backend == "fallback-board"
        assert scene.actor is not None

    def test_load_with_vtk_fallback_on_non_stl(self, tmp_path):
        # Write a dummy file that is not a valid STL
        step_file = tmp_path / "board.step"
        step_file.write_text("invalid step data", encoding="utf-8")
        loader = StepSceneLoader()
        scene = loader.load(step_file)
        # VTK STL reader may fail gracefully → fallback
        assert not scene.ok or scene.backend in ("vtk-stl", "fallback")


class TestLoadedScene:
    def test_dataclass_fields(self):
        scene = LoadedScene(
            ok=True,
            source_path=Path("x.step"),
            backend="test",
            actor=None,
            issues=[
                SceneLoadIssue(
                    SceneLoadSeverity.WARNING, "TEST", "test message"
                )
            ],
        )
        assert scene.ok
        assert len(scene.issues) == 1
        assert scene.issues[0].severity == SceneLoadSeverity.WARNING
