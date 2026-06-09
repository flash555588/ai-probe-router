"""Tests for KiCad Plugin Shell report loading and 3D view."""

import importlib.util
import json
from pathlib import Path

import pytest

from ai_probe_router.ui.report_loader import (
    FootprintEntry,
    IssueEntry,
    load_footprint_preview,
    load_readiness,
    load_resource_allocation,
    load_resource_optimization,
)
from ai_probe_router.ui.vtk_3d_view import _create_board_plane, build_3d_scene


def _write_json(tmp_path: Path, name: str, data: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class TestReportLoader:
    def test_load_footprint_preview(self, tmp_path):
        data = {
            "ok": True,
            "has_warnings": False,
            "planned_footprints": [
                {
                    "module_name": "mod_a",
                    "reference": "U1",
                    "footprint": "fp",
                    "x_mm": 10.0,
                    "y_mm": 20.0,
                    "rotation_deg": 0.0,
                    "side": "top",
                    "role": "mcu",
                }
            ],
            "issues": [
                {
                    "severity": "warning",
                    "code": "DENSE_REGION",
                    "message": "dense",
                    "module_name": None,
                    "reference": None,
                }
            ],
        }
        path = _write_json(tmp_path, "footprint_preview_report.json", data)
        result = load_footprint_preview(path)
        assert result is not None
        assert result.ok
        assert len(result.footprints) == 1
        assert result.footprints[0].reference == "U1"
        assert len(result.issues) == 1

    def test_load_footprint_preview_missing_file(self, tmp_path):
        result = load_footprint_preview(tmp_path / "missing.json")
        assert result is None

    def test_load_resource_allocation(self, tmp_path):
        data = {
            "ok": True,
            "warnings": [],
            "errors": [],
            "bus_result": {
                "assignments": [
                    {
                        "bus_type": "i2c",
                        "bus_id": 1,
                        "module_name": "sensor",
                        "instance_id": "U1",
                        "address": "0x50",
                    }
                ]
            },
            "power_result": {
                "domains": [
                    {
                        "domain_name": "3V3",
                        "voltage": 3.3,
                        "budget_ma": 500.0,
                        "requested_ma": 100.0,
                        "headroom_percent": 80.0,
                    }
                ]
            },
        }
        path = _write_json(tmp_path, "resource_allocation_report.json", data)
        result = load_resource_allocation(path)
        assert result is not None
        assert result.ok
        assert len(result.buses) == 1
        assert result.buses[0].bus_type == "i2c"
        assert len(result.power) == 1
        assert result.power[0].domain == "3V3"

    def test_load_resource_optimization(self, tmp_path):
        data = {
            "schema_version": 1,
            "ok": True,
            "recommendations": [
                {
                    "recommendation_id": "ROPT-BUS-SPLIT-I2C-1",
                    "severity": "warning",
                    "category": "bus",
                    "scope": "I2C-1",
                    "module_name": "",
                    "applies_to": ["sensor"],
                    "current_assignment": "I2C-1 has 5 modules",
                    "recommendation": "Move lower-priority modules to I2C-2.",
                    "expected_impact": "Reduces bus fanout.",
                    "safe_to_apply_automatically": False,
                }
            ],
            "notes": ["advisory"],
        }
        path = _write_json(tmp_path, "resource_optimization_report.json", data)
        result = load_resource_optimization(path)
        assert result is not None
        assert result.ok
        assert len(result.recommendations) == 1
        assert result.recommendations[0].scope == "I2C-1"
        assert not result.recommendations[0].safe_to_apply_automatically

    def test_load_readiness(self, tmp_path):
        data = {
            "verdict": "PASS_WITH_REVIEW",
            "run_id": "APR-TEST",
            "blockers": [],
            "warnings": [
                {
                    "severity": "warning",
                    "source": "footprint_preview",
                    "message": "dense region",
                }
            ],
        }
        path = _write_json(tmp_path, "readiness_report.json", data)
        result = load_readiness(path)
        assert result is not None
        assert result.verdict == "PASS_WITH_REVIEW"
        assert len(result.warnings) == 1
        assert len(result.blockers) == 0


@pytest.mark.skipif(importlib.util.find_spec("vtkmodules") is None, reason="vtk not installed")
class TestVtk3DView:
    def test_build_3d_scene(self):
        fps = [
            FootprintEntry(
                module_name="a",
                reference="U1",
                footprint="fp",
                x_mm=10.0,
                y_mm=20.0,
                rotation_deg=0.0,
                side="top",
                role="mcu",
            )
        ]
        issues = [
            IssueEntry(
                severity="error",
                code="COLLISION",
                message="collides",
                module_name="a",
                reference="U1",
            )
        ]
        renderer = build_3d_scene(fps, issues)
        assert renderer.GetActors().GetNumberOfItems() >= 2  # board + box

    def test_create_board_plane(self):
        actor = _create_board_plane(50.0, 30.0)
        assert actor is not None


class TestPluginShellImport:
    def test_can_import_without_pyqt6_runtime(self):
        """Module should parse even if PyQt6 is not importable at runtime.

        We verify this by simply importing the module — test collection
        itself would fail if the import were unconditional.
        """
        from ai_probe_router.ui.plugin_shell import KiCadPluginShell
        assert KiCadPluginShell is not None

    def test_shell_loads_reports(self, tmp_path):
        from ai_probe_router.ui.plugin_shell import KiCadPluginShell

        # Write dummy reports
        _write_json(
            tmp_path,
            "footprint_preview_report.json",
            {"ok": True, "has_warnings": False, "planned_footprints": [], "issues": []},
        )
        _write_json(
            tmp_path,
            "readiness_report.json",
            {"verdict": "PASS", "run_id": "", "blockers": [], "warnings": []},
        )
        _write_json(
            tmp_path,
            "resource_optimization_report.json",
            {"ok": True, "recommendations": [], "notes": []},
        )
        shell = KiCadPluginShell(tmp_path)
        shell.load_reports()
        assert shell.footprint_data is not None
        assert shell.resource_optimization_data is not None
        assert shell.readiness_data is not None
        assert shell.readiness_data.verdict == "PASS"

    def test_shell_can_disable_3d_without_vtk(self, tmp_path, monkeypatch):
        from ai_probe_router.ui import plugin_shell

        class FakeTabs:
            def __init__(self):
                self.labels = []

            def addTab(self, _widget, label):
                self.labels.append(label)

        class FakeQtWidgets:
            @staticmethod
            def QTabWidget():
                return tabs

        class FakeWindow:
            def setCentralWidget(self, widget):
                self.central_widget = widget

        tabs = FakeTabs()
        shell = plugin_shell.KiCadPluginShell(tmp_path, enable_3d=False)
        shell._window = FakeWindow()

        monkeypatch.setattr(plugin_shell, "_require_pyqt6", lambda: FakeQtWidgets)
        monkeypatch.setattr(
            plugin_shell.KiCadPluginShell,
            "_build_footprint_tab",
            lambda self: object(),
        )
        monkeypatch.setattr(
            plugin_shell.KiCadPluginShell,
            "_build_resource_tab",
            lambda self: object(),
        )
        monkeypatch.setattr(
            plugin_shell.KiCadPluginShell,
            "_build_route_tab",
            lambda self: object(),
        )
        monkeypatch.setattr(
            plugin_shell.KiCadPluginShell,
            "_build_3d_tab",
            lambda self: (_ for _ in ()).throw(AssertionError("3D tab should be disabled")),
        )

        shell._build_tabs()

        assert tabs.labels == ["Footprint Preview", "Resource Allocation", "Route Import"]
        assert shell._window.central_widget is tabs
