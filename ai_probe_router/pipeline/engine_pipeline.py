"""Engine pipeline stages.

Replaces the monolithic ``engine.run()`` with a sequence of explicit,
individually-testable stages.  Each stage receives a shared context and
mutates it in place.  The core ``engine.py`` keeps ``_run_phase1`` and
``_run_phase2`` as the heavy-lifting implementations; this file only
orchestrates the surrounding flow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..config import ProjectConfig
from ..eda_adapters.kicad.pcb_parser import parse_pcb
from ..eda_adapters.kicad.pcb_writer import write_pcb
from ..eda_adapters.kicad.sch_parser import parse_schematic
from ..eda_adapters.kicad.sch_writer import write_schematic
from ..models.board import Board, Schematic
from ..verification.decision_manifest import read_prior_manifest
from ..verification.pin_report import PinMapReport
from ..verification.report import CoverageReport


@dataclass
class PipelineContext:
    """Mutable bag of state passed through every pipeline stage."""

    cfg: ProjectConfig
    project_dir: Path
    run_id: str = ""
    out_dir: Path | None = None
    prior_manifest: dict | None = None
    board: Board | None = None
    sch: Schematic | None = None
    coverage: CoverageReport | None = None
    pin_report: PinMapReport | None = None
    module_plan = None
    out_pcb_path: Path | None = None
    out_sch_path: Path | None = None
    mfg_report = None
    dp_report = None
    autoroute_result = None
    notes: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return self.module_plan is not None and getattr(
            self.module_plan, "blocked", False
        )


def load_inputs(ctx: PipelineContext) -> None:
    """Stage 1: parse PCB and schematic if present."""
    base = ctx.project_dir
    cfg = ctx.cfg
    pcb_path = base / cfg.board_file
    sch_path = base / cfg.schematic_file

    if cfg.board_file and pcb_path.is_file():
        ctx.board = parse_pcb(pcb_path)
    if cfg.schematic_file and sch_path.is_file():
        ctx.sch = parse_schematic(sch_path)


def prepare_output(ctx: PipelineContext) -> None:
    """Stage 2: build run id, output directory, read prior manifest."""
    from .run_id import build_run_id

    base = ctx.project_dir
    ctx.run_id = build_run_id(ctx.cfg, base)
    ctx.out_dir = base / "output"
    ctx.out_dir.mkdir(exist_ok=True)
    ctx.prior_manifest = read_prior_manifest(
        ctx.out_dir / "decision_manifest.json"
    )


def run_module_planning_stage(ctx: PipelineContext) -> None:
    """Stage 3: module planning and early-exit handling."""
    from ..pipeline.module_planning import run_module_planning

    ctx.module_plan = run_module_planning(ctx.cfg, ctx.board)


def blocked_early_return(ctx: PipelineContext) -> CoverageReport:
    """Return a minimal coverage report when module planning blocks."""
    from ..pipeline.delivery_artifacts import write_delivery_artifacts
    from ..pipeline.module_planning import write_module_planning_reports
    from ..verification.manufacturing_report import generate_manufacturing_report
    from ..verification.report import CoverageReport

    coverage = CoverageReport(
        run_id=ctx.run_id,
        total_nets_requested=len(ctx.cfg.nets_to_expose),
        missing=len(ctx.cfg.nets_to_expose),
    )
    coverage.notes.append(
        "Module planning blocked generation; no PCB or schematic changes were written"
    )
    mfg_report = generate_manufacturing_report(ctx.board, coverage)
    write_module_planning_reports(ctx.out_dir, ctx.run_id, ctx.module_plan)
    mfg_report.write(ctx.out_dir / "manufacturing_report.txt")
    write_delivery_artifacts(
        out_dir=ctx.out_dir,
        cfg=ctx.cfg,
        run_id=ctx.run_id,
        board=ctx.board,
        coverage=coverage,
        manufacturing_report=mfg_report,
        prior_manifest=ctx.prior_manifest,
        module_library_preflight_result=ctx.module_plan.module_library_preflight_result,
        module_selection=ctx.module_plan.module_selection,
        module_graph_result=ctx.module_plan.module_graph_result,
        module_compatibility_result=ctx.module_plan.module_compatibility_result,
        module_placement_result=ctx.module_plan.module_placement_result,
        module_instantiation_result=ctx.module_plan.module_instantiation_result,
        routing_feasibility=ctx.module_plan.routing_feasibility,
        resource_allocation_result=ctx.module_plan.resource_allocation_result,
        footprint_preview_result=ctx.module_plan.footprint_preview_result,
        autoroute_result=None,
    )
    return coverage


def run_pin_mapping_stage(ctx: PipelineContext) -> None:
    """Stage 4: Phase 2 pin mapping (runs before placement in existing order)."""
    from .phase2_pinmap import run_phase2

    if ctx.cfg.development_board is not None and ctx.cfg.nets_to_expose:
        ctx.pin_report = run_phase2(
            ctx.cfg, ctx.board, ctx.sch, ctx.cfg.development_board
        )


def run_probe_placement_stage(ctx: PipelineContext) -> None:
    """Stage 5: Phase 1 probe placement and routing."""
    from .phase1_probes import run_phase1

    ctx.coverage = run_phase1(ctx.cfg, ctx.board, ctx.sch)
    ctx.coverage.run_id = ctx.run_id


def instantiate_modules_stage(ctx: PipelineContext) -> None:
    """Stage 6: instantiate module sheets into schematic."""
    from ..synthesis.module_instantiator import instantiate_module_sheets

    if ctx.module_plan.module_graph_result is not None:
        ctx.module_plan.module_instantiation_result = instantiate_module_sheets(
            ctx.sch,
            ctx.module_plan.module_graph_result.graph,
            ctx.out_dir,
            run_id=ctx.run_id,
        )


def validate_and_write_board_stage(ctx: PipelineContext) -> None:
    from ..ai.net_classifier import classify_net, classify_net_detailed
    from ..ai.rule_generator import generate_rules
    from ..eda_adapters.kicad.pcb_writer import add_net_class
    from ..eda_adapters.kicad.project_writer import write_project_file
    from ..solvers.constraint_checker import validate_all_probes

    cfg = ctx.cfg
    board = ctx.board
    coverage = ctx.coverage
    out_dir = ctx.out_dir
    pcb_path = cfg.board_file
    sch_path = cfg.schematic_file

    if board is not None:
        probe_data = [
            (fp.pads[0].x, fp.pads[0].y, fp.pads[0].net_name)
            for fp in board.footprints
            if fp.ref.startswith("TP") and fp.pads
        ]
        if probe_data:
            validation = validate_all_probes(
                probe_data, board, cfg.constraints, cfg.probe,
            )
            coverage.constraint_violations = len(validation.violations)
            coverage.constraint_ok = validation.ok
            coverage.constraint_messages = [v.message for v in validation.violations]

        net_names = [e.net_name for e in coverage.entries]
        roles = {n: classify_net(n) for n in net_names}
        sub_roles_map = {
            n: classify_net_detailed(n, cfg.mcu_profile)[1]
            for n in net_names
        }
        rules = generate_rules(roles, cfg.nets_to_expose, net_sub_roles=sub_roles_map)
        for r in rules.net_rules:
            dp_width = r.trace_width_mm if r.differential_pair else None
            dp_gap = 0.15 if r.differential_pair else None
            if r.differential_pair and cfg.impedance_control.has_rules():
                for rule_name, rule in cfg.impedance_control.rules.items():
                    if rule_name.lower() in r.net_name.lower():
                        dp_width = rule.diff_pair_width_mm
                        dp_gap = rule.diff_pair_gap_mm
                        break
            add_net_class(
                board,
                name=f"NET_{r.net_name}",
                description=r.role.name.lower(),
                clearance=r.clearance_mm,
                trace_width=r.trace_width_mm,
                diff_pair_width=dp_width,
                diff_pair_gap=dp_gap,
            )

        out_pcb = out_dir / pcb_path
        write_pcb(board, out_pcb)
        ctx.out_pcb_path = out_pcb
        source_pro = (ctx.project_dir / pcb_path).with_suffix(".kicad_pro")
        write_project_file(out_pcb, cfg.constraints, source_project=source_pro)

    if ctx.sch is not None:
        out_sch = out_dir / sch_path
        write_schematic(ctx.sch, out_sch)
        ctx.out_sch_path = out_sch


def native_validation_stage(ctx: PipelineContext) -> None:
    """Stage 8: KiCad ERC/DRC native validation."""
    from ..pipeline.native_tools import (
        apply_native_validation,
        run_native_validation,
    )

    apply_native_validation(
        ctx.coverage,
        run_native_validation(
            ctx.out_pcb_path, ctx.out_sch_path, ctx.out_dir
        ),
        ctx.cfg,
        defer_failures=True,
    )


def report_generation_stage(ctx: PipelineContext) -> None:
    """Stage 9: manufacturing, diff-pair, design-review reports."""
    from ..ai.design_review import run_design_review
    from ..pipeline.module_planning import write_module_planning_reports
    from ..verification.diff_pair_skew_report import generate_diff_pair_skew_report
    from ..verification.manufacturing_report import generate_manufacturing_report

    cfg = ctx.cfg
    out_dir = ctx.out_dir

    write_module_planning_reports(out_dir, ctx.run_id, ctx.module_plan)
    if ctx.pin_report is not None:
        ctx.pin_report.write(out_dir / "pin_mapping_report.txt")

    ctx.mfg_report = generate_manufacturing_report(ctx.board, ctx.coverage)
    ctx.mfg_report.write(out_dir / "manufacturing_report.txt")

    ctx.dp_report = generate_diff_pair_skew_report(ctx.coverage, cfg.nets_to_expose)
    ctx.dp_report.write(out_dir / "diff_pair_skew_report.txt")
    if not ctx.dp_report.ok() and ctx.dp_report.pairs:
        failed = sum(1 for p in ctx.dp_report.pairs if not p.ok)
        ctx.coverage.notes.append(
            f"Diff pair skew: {failed} pair(s) exceed threshold"
        )

    if ctx.sch is not None:
        review = run_design_review(ctx.sch, ctx.board, cfg.mcu_profile)
        if review.findings:
            review_path = out_dir / "design_review_report.txt"
            review_path.write_text(review.summary(), encoding="utf-8")
            ctx.coverage.notes.append(
                f"Design review: {review.error_count} errors, "
                f"{review.warning_count} warnings"
            )


def autorouter_stage(ctx: PipelineContext) -> None:
    """Stage 10: external autorouter (FreeRouting)."""
    from ..pipeline.autorouter import run_autorouter

    ctx.autoroute_result = run_autorouter(
        ctx.cfg, ctx.coverage, ctx.board, ctx.out_dir
    )


def thermal_analysis_stage(ctx: PipelineContext) -> None:
    """Stage 11: thermal analysis export."""
    from .thermal_export import write_thermal_analysis_export

    if ctx.cfg.thermal_analysis.enabled and ctx.board is not None:
        thermal_path = write_thermal_analysis_export(
            ctx.board, ctx.cfg, ctx.out_dir
        )
        ctx.coverage.notes.append(
            f"Thermal simulation export: {thermal_path.name}"
        )


def manufacturing_export_stage(ctx: PipelineContext) -> None:
    """Stage 12: Gerber/drill/PnP manufacturing exports."""
    from ..pipeline.native_tools import run_manufacturing_exports

    mfg_dir = ctx.out_dir / "manufacturing"
    if ctx.out_pcb_path is not None:
        run_manufacturing_exports(
            ctx.cfg,
            ctx.coverage,
            ctx.out_pcb_path,
            mfg_dir,
            defer_failures=True,
        )


def delivery_artifact_stage(ctx: PipelineContext) -> None:
    """Stage 13: write decision manifest and readiness report."""
    from ..pipeline.delivery_artifacts import write_delivery_artifacts

    write_delivery_artifacts(
        out_dir=ctx.out_dir,
        cfg=ctx.cfg,
        run_id=ctx.run_id,
        board=ctx.board,
        coverage=ctx.coverage,
        manufacturing_report=ctx.mfg_report,
        prior_manifest=ctx.prior_manifest,
        module_library_preflight_result=ctx.module_plan.module_library_preflight_result,
        module_selection=ctx.module_plan.module_selection,
        module_graph_result=ctx.module_plan.module_graph_result,
        module_compatibility_result=ctx.module_plan.module_compatibility_result,
        module_placement_result=ctx.module_plan.module_placement_result,
        module_instantiation_result=ctx.module_plan.module_instantiation_result,
        routing_feasibility=ctx.module_plan.routing_feasibility,
        pin_report=ctx.pin_report,
        diff_pair_report=ctx.dp_report,
        autoroute_result=ctx.autoroute_result,
        resource_allocation_result=ctx.module_plan.resource_allocation_result,
        footprint_preview_result=ctx.module_plan.footprint_preview_result,
    )


def signoff_stage(ctx: PipelineContext) -> None:
    """Stage 14: raise deferred signoff failures if configured."""
    raise_deferred_signoff_failure(ctx.cfg, ctx.coverage)


def raise_deferred_signoff_failure(
    cfg: ProjectConfig, coverage: CoverageReport,
) -> None:
    if not (
        cfg.process_controls.strict_signoff
        or cfg.process_controls.require_manufacturing_exports
    ):
        return
    blocking_prefixes = (
        "DRC validation failed:",
        "DRC validation skipped:",
        "ERC validation failed:",
        "ERC validation skipped:",
        "Schematic parity validation failed:",
        "Schematic parity validation skipped:",
        "Gerber export failed:",
        "Drill export failed:",
        "Pick&Place export failed:",
    )
    for note in coverage.notes:
        if note.startswith(blocking_prefixes):
            raise RuntimeError(note)
