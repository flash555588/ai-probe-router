"""Cross-PR pipeline integration test.

Verifies that output artifacts from PR2–PR7 can be loaded together
without errors by the unified report reader.
"""

import json
from pathlib import Path

from ai_probe_router.report_utils import load_all_reports
from ai_probe_router.solvers.resource_allocator_report import (
    generate_resource_allocation_json,
)
from ai_probe_router.verification.footprint_preview_report import (
    generate_footprint_preview_json,
)


def _write_json(tmp_path: Path, name: str, data: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class TestPipelineIntegration:
    def test_load_all_reports_from_output_dir(self, tmp_path):
        """PR2–PR7 reports load together without error."""
        # PR6 — footprint preview
        fp_data = {
            "schema_version": 1,
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
            "issues": [],
        }
        _write_json(tmp_path, "footprint_preview_report.json", fp_data)

        # PR5 — resource allocation
        ra_data = {
            "schema_version": 1,
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
                ],
                "conflicts": [],
                "near_limit": False,
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
                ],
                "overload_domains": [],
                "near_limit_domains": [],
            },
        }
        _write_json(tmp_path, "resource_allocation_report.json", ra_data)

        # PR2 — readiness
        rd_data = {
            "verdict": "PASS",
            "run_id": "APR-TEST",
            "blockers": [],
            "warnings": [],
        }
        _write_json(tmp_path, "readiness_report.json", rd_data)

        reports = load_all_reports(tmp_path)
        assert reports.has_any
        assert reports.footprint_preview is not None
        assert reports.resource_allocation is not None
        assert reports.readiness is not None
        assert reports.all_ok
        assert reports.total_blockers == 0
        assert reports.total_warnings == 0

    def test_unified_reports_counts_blockers_and_warnings(self, tmp_path):
        fp_data = {
            "schema_version": 1,
            "ok": False,
            "has_warnings": True,
            "planned_footprints": [],
            "issues": [
                {
                    "severity": "error",
                    "code": "COLLISION",
                    "message": "collides",
                    "module_name": None,
                    "reference": None,
                },
                {
                    "severity": "warning",
                    "code": "DENSE",
                    "message": "dense",
                    "module_name": None,
                    "reference": None,
                },
            ],
        }
        _write_json(tmp_path, "footprint_preview_report.json", fp_data)
        _write_json(
            tmp_path,
            "resource_allocation_report.json",
            {
                "schema_version": 1,
                "ok": True,
                "warnings": ["warn"],
                "errors": [],
                "bus_result": {"assignments": [], "conflicts": [], "near_limit": False},
                "power_result": {
                    "domains": [],
                    "overload_domains": [],
                    "near_limit_domains": [],
                },
            },
        )
        _write_json(
            tmp_path,
            "readiness_report.json",
            {
                "verdict": "BLOCKED",
                "run_id": "",
                "blockers": [
                    {"severity": "error", "source": "test", "message": "b"}
                ],
                "warnings": [],
            },
        )

        reports = load_all_reports(tmp_path)
        assert not reports.all_ok
        assert reports.total_blockers == 2  # 1 fp error + 1 readiness blocker
        assert reports.total_warnings == 2  # 1 fp warning + 1 resource warning

    def test_schema_version_present_in_footprint_report(self):
        from ai_probe_router.models.footprint_preview import FootprintPreviewResult

        result = FootprintPreviewResult()
        json_text = generate_footprint_preview_json(result)
        data = json.loads(json_text)
        assert data["schema_version"] == 1

    def test_schema_version_present_in_resource_report(self):
        from ai_probe_router.solvers.resource_allocator import ResourceAllocationResult

        result = ResourceAllocationResult()
        json_text = generate_resource_allocation_json(result)
        data = json.loads(json_text)
        assert data["schema_version"] == 1

    def test_readiness_codes_enum_lookup(self):
        from ai_probe_router.models.readiness_codes import ReadinessCode, code_severity

        assert code_severity(ReadinessCode.POWER_DOMAIN_OVERLOAD) == "error"
        assert code_severity(ReadinessCode.BUS_ALLOCATION_NEAR_LIMIT) == "warning"
        assert code_severity("POWER_DOMAIN_OVERLOAD") == "error"
        assert code_severity("UNKNOWN_CODE") == "warning"

    def test_coordinate_frame_roundtrip(self):
        from ai_probe_router.ui.coordinate_transform import (
            fit_frame_to_board,
        )

        frame = fit_frame_to_board(100.0, 50.0)
        wx, wy, wz = frame.pcb_to_world(10.0, 20.0, "top")
        assert wz == frame.top_z
        x_back, y_back = frame.world_to_pcb(wx, wy)
        assert abs(x_back - 10.0) < 0.001
        assert abs(y_back - 20.0) < 0.001

    def test_plugin_shell_config_from_yaml(self, tmp_path):
        from ai_probe_router.config import load_config

        cfg_path = tmp_path / "test.yaml"
        cfg_path.write_text(
            "project:\n"
            "  board_file: board.kicad_pcb\n"
            "nets_to_expose:\n"
            "  - net: TEST_NET\n"
            "    style: via\n"
            "plugin_shell:\n"
            "  step_file: board.step\n"
            "  enable_3d: true\n",
            encoding="utf-8",
        )
        cfg = load_config(cfg_path)
        assert cfg.plugin_shell.step_file == "board.step"
        assert cfg.plugin_shell.enable_3d is True
        assert cfg.plugin_shell.fallback_to_2d_board is True
    def test_plugin_report_model_joins_all_reports(self, tmp_path):
        fp_data = {
            "schema_version": 1,
            "ok": True,
            "has_warnings": False,
            "planned_footprints": [
                {
                    "module_name": "test_mod",
                    "reference": "U1",
                    "footprint": "fp",
                    "x_mm": 10.0,
                    "y_mm": 20.0,
                    "rotation_deg": 0.0,
                    "side": "top",
                }
            ],
            "issues": [],
        }
        ra_data = {
            "schema_version": 1,
            "ok": True,
            "bus_result": {
                "assignments": [
                    {
                        "bus_type": "i2c",
                        "bus_id": 1,
                        "module_name": "test_mod",
                        "instance_id": "U1",
                        "address": "0x50",
                    }
                ]
            },
            "power_result": {"domains": []},
            "warnings": [],
            "errors": [],
        }
        rd_data = {
            "verdict": "PASS",
            "run_id": "APR-PIPELINE",
            "blockers": [],
            "warnings": [],
        }
        _write_json(tmp_path, "footprint_preview_report.json", fp_data)
        _write_json(tmp_path, "resource_allocation_report.json", ra_data)
        _write_json(tmp_path, "readiness_report.json", rd_data)

        reports = load_all_reports(tmp_path)
        from ai_probe_router.ui.report_model import PluginReportModel

        model = PluginReportModel(reports)
        summary = model.module_summary("test_mod", "U1")
        assert summary.footprint == "fp"
        assert summary.reference == "U1"
        assert len(summary.resource_assignments) == 1
        assert summary.resource_assignments[0]["bus_type"] == "i2c"

    def test_step_scene_loader_fallback_on_missing_file(self, tmp_path):
        from ai_probe_router.ui.step_scene_loader import StepSceneLoader

        loader = StepSceneLoader()
        scene = loader.load(tmp_path / "missing.step")
        assert not scene.ok
        assert scene.backend == "fallback"
        assert any(i.code == "STEP_FILE_NOT_FOUND" for i in scene.issues)

    def test_severity_filter_state_in_pipeline(self):
        from ai_probe_router.ui.severity_filter import SeverityFilterState

        state = SeverityFilterState(
            show_error=True, show_warning=False, show_info=False
        )
        assert state.allows("error")
        assert not state.allows("warning")
        assert not state.allows("info")
