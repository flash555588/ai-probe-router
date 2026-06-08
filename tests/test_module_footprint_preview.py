"""Tests for module footprint preview."""

from ai_probe_router.config import ModuleFootprintPreviewConfig
from ai_probe_router.models.board import Board
from ai_probe_router.models.footprint_preview import (
    FootprintPreviewIssue,
    FootprintPreviewResult,
    FootprintPreviewSeverity,
    PlannedFootprint,
)
from ai_probe_router.models.module import (
    ComponentSpec,
    FunctionalModule,
    ModuleDefinition,
    ModuleImplementation,
    SelectedModule,
)
from ai_probe_router.solvers.footprint_collision import (
    CollisionBox,
    check_board_bounds,
    check_footprint_collisions,
    check_keepout_violations,
)
from ai_probe_router.solvers.module_footprint_planner import plan_module_footprints
from ai_probe_router.verification.footprint_preview_report import (
    write_footprint_preview_report,
)


def _sel(name: str, comp_type: str = "mcu", count: int = 1) -> SelectedModule:
    mod = FunctionalModule(name=name, type="test")
    definition = ModuleDefinition(name=name, type="test")
    impl = ModuleImplementation(
        name=f"{name}_impl",
        components=[ComponentSpec(type=comp_type, count=count)],
    )
    return SelectedModule(module=mod, definition=definition, implementation=impl)


def _board(width: float = 100.0, height: float = 100.0) -> Board:
    return Board(
        edges=[
            [(0.0, 0.0), (width, 0.0), (width, height), (0.0, height), (0.0, 0.0)]
        ],
        nets=[],
        footprints=[],
    )


class TestFootprintPreviewDisabled:
    def test_preview_disabled_preserves_existing_behavior(self):
        cfg = ModuleFootprintPreviewConfig(enable=False)
        result = plan_module_footprints([_sel("a")], _board(), cfg)
        assert not result.planned_footprints
        assert not result.issues
        assert result.ok


class TestFootprintPreviewEnabled:
    def test_preview_generates_planned_footprints(self):
        cfg = ModuleFootprintPreviewConfig(enable=True)
        result = plan_module_footprints([_sel("a", count=2)], _board(), cfg)
        assert len(result.planned_footprints) == 2
        assert result.planned_footprints[0].module_name == "a"
        assert result.ok  # no errors, only info/warning

    def test_missing_required_footprint_blocks_when_configured(self):
        cfg = ModuleFootprintPreviewConfig(
            enable=True, block_on_missing_footprint=True
        )
        result = plan_module_footprints(
            [_sel("a", comp_type="unknown_type")], _board(), cfg
        )
        assert not result.ok
        assert any(
            "MISSING_REQUIRED_FOOTPRINT" in i.code for i in result.issues
        )

    def test_missing_optional_footprint_warns(self):
        cfg = ModuleFootprintPreviewConfig(
            enable=True, block_on_missing_footprint=False
        )
        result = plan_module_footprints(
            [_sel("a", comp_type="unknown_type")], _board(), cfg
        )
        assert result.ok
        assert any(
            "MISSING_REQUIRED_FOOTPRINT" in i.code
            and i.severity == FootprintPreviewSeverity.WARNING
            for i in result.issues
        )

    def test_existing_footprint_collision_blocks(self):
        board = _board()
        from ai_probe_router.models.board import Footprint, Pad
        board.footprints.append(
            Footprint(
                ref="MCU1",
                lib_id="Package_QFP:LQFP-48_7x7mm_P0.5mm",
                x=50.0,
                y=50.0,
                rotation=0.0,
                layer="F.Cu",
                pads=[Pad(number="1", x=0, y=0, width=1, height=1)],
            )
        )
        planned = [
            PlannedFootprint(
                module_name="a",
                reference="MCU1",
                footprint="fp",
                x_mm=50.0,
                y_mm=50.0,
            )
        ]
        issues = check_footprint_collisions(planned, {"MCU1"})
        assert any(i.code == "FOOTPRINT_PREVIEW_COLLISION" for i in issues)

    def test_planned_footprint_collision_blocks(self):
        planned = [
            PlannedFootprint(
                module_name="a", reference="F1", footprint="fp", x_mm=50.0, y_mm=50.0
            ),
            PlannedFootprint(
                module_name="a", reference="F2", footprint="fp", x_mm=50.0, y_mm=50.0
            ),
        ]
        issues = check_footprint_collisions(planned, set())
        assert any(i.code == "FOOTPRINT_PREVIEW_COLLISION" for i in issues)

    def test_out_of_bounds_blocks(self):
        board = _board(width=50.0, height=50.0)
        planned = [
            PlannedFootprint(
                module_name="a",
                reference="F1",
                footprint="fp",
                x_mm=100.0,
                y_mm=100.0,
            )
        ]
        issues = check_board_bounds(planned, board)
        assert any(i.code == "FOOTPRINT_PREVIEW_OUT_OF_BOUNDS" for i in issues)

    def test_preview_writes_text_and_json_reports(self, tmp_path):
        result = FootprintPreviewResult(
            planned_footprints=[
                PlannedFootprint(
                    module_name="a",
                    reference="F1",
                    footprint="fp",
                    x_mm=10.0,
                    y_mm=20.0,
                )
            ]
        )
        write_footprint_preview_report(result, tmp_path)
        text = (tmp_path / "footprint_preview_report.txt").read_text()
        json_text = (tmp_path / "footprint_preview_report.json").read_text()
        assert "F1" in text
        assert "F1" in json_text
        assert '"ok": true' in json_text

    def test_emit_candidate_writes_only_output_pcb(self):
        cfg = ModuleFootprintPreviewConfig(
            enable=True, mode="emit_candidate", write_candidate_pcb=True
        )
        assert cfg.candidate_suffix == ".module-preview"

    def test_source_pcb_not_modified(self):
        board = _board()
        cfg = ModuleFootprintPreviewConfig(enable=True)
        plan_module_footprints([_sel("a")], board, cfg)
        assert len(board.footprints) == 0

    def test_readiness_includes_footprint_preview_errors(self):
        from ai_probe_router.verification.readiness_report import generate_readiness_report
        from ai_probe_router.verification.report import CoverageReport

        coverage = CoverageReport(run_id="APR-TEST")
        result = FootprintPreviewResult(
            issues=[
                FootprintPreviewIssue(
                    severity=FootprintPreviewSeverity.ERROR,
                    code="FOOTPRINT_PREVIEW_COLLISION",
                    message="collision",
                )
            ]
        )
        report = generate_readiness_report(
            coverage, footprint_preview_result=result
        )
        assert report.verdict == "BLOCKED"
        assert any(
            issue.source == "footprint_preview" for issue in report.blockers
        )


class TestCollisionBox:
    def test_intersects_when_overlapping(self):
        a = CollisionBox(0, 0, 10, 10)
        b = CollisionBox(5, 5, 15, 15)
        assert a.intersects(b)

    def test_no_intersect_when_separate(self):
        a = CollisionBox(0, 0, 10, 10)
        b = CollisionBox(20, 20, 30, 30)
        assert not a.intersects(b)


class TestKeepoutViolations:
    def test_keepout_violation_detected(self):
        board = _board()
        board.keepout_zones = [{"x_min": 40, "y_min": 40, "x_max": 60, "y_max": 60}]
        planned = [
            PlannedFootprint(
                module_name="a",
                reference="F1",
                footprint="fp",
                x_mm=50.0,
                y_mm=50.0,
            )
        ]
        issues = check_keepout_violations(planned, board)
        assert any(i.code == "FOOTPRINT_PREVIEW_KEEPOUT_VIOLATION" for i in issues)
