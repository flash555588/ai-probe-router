"""Core engine: thin orchestrator over the staged pipeline.

The heavy lifting lives in ``pipeline/``:

- ``pipeline.engine_pipeline``  — stage definitions and shared context
- ``pipeline.phase1_probes``    — probe placement and escape routing
- ``pipeline.phase2_pinmap``    — development-board pin mapping
- ``pipeline.run_id``           — deterministic run-id fingerprinting
- ``pipeline.thermal_export``   — thermal analysis export

Stages are invoked through the ``engine_pipeline`` module namespace so they
can be monkeypatched at a single canonical location.
"""

from __future__ import annotations

from pathlib import Path

from .config import ProjectConfig
from .pipeline import engine_pipeline as stages
from .verification.pin_report import PinMapReport
from .verification.report import CoverageReport


def run(
    cfg: ProjectConfig, project_dir: str | Path,
) -> tuple[CoverageReport, PinMapReport | None]:
    """Orchestrate the full probe generation pipeline."""
    ctx = stages.PipelineContext(cfg=cfg, project_dir=Path(project_dir))

    stages.load_inputs(ctx)
    stages.prepare_output(ctx)
    stages.run_module_planning_stage(ctx)

    if ctx.blocked:
        coverage = stages.blocked_early_return(ctx)
        return coverage, None

    stages.run_pin_mapping_stage(ctx)
    stages.run_probe_placement_stage(ctx)
    stages.instantiate_modules_stage(ctx)
    stages.validate_and_write_board_stage(ctx)
    stages.native_validation_stage(ctx)
    stages.report_generation_stage(ctx)
    stages.autorouter_stage(ctx)
    stages.thermal_analysis_stage(ctx)
    stages.manufacturing_export_stage(ctx)
    stages.delivery_artifact_stage(ctx)
    stages.signoff_stage(ctx)

    return ctx.coverage, ctx.pin_report
