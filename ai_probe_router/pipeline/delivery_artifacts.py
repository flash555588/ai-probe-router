"""Delivery artifact writing stage for engine runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import ProjectConfig
from ..models.board import Board
from ..verification.decision_manifest import (
    artifact_paths,
    collect_artifact_manifest,
    write_decision_manifest,
)
from ..verification.design_process_report import generate_design_process_report
from ..verification.diff_pair_skew_report import DiffPairSkewReport
from ..verification.manufacturing_report import ManufacturingReport
from ..verification.readiness_report import ReadinessReport, generate_readiness_report
from ..verification.report import CoverageReport


@dataclass(frozen=True)
class DeliveryArtifactResult:
    process_report: Any
    readiness_report: ReadinessReport
    manifest: dict[str, Any]
    artifacts: list[dict[str, Any]]


def write_delivery_artifacts(
    *,
    out_dir: Path,
    cfg: ProjectConfig,
    run_id: str,
    board: Board | None,
    coverage: CoverageReport,
    manufacturing_report: ManufacturingReport,
    prior_manifest: dict[str, Any] | None = None,
    module_library_preflight_result=None,
    module_selection=None,
    module_graph_result=None,
    module_compatibility_result=None,
    module_placement_result=None,
    module_instantiation_result=None,
    routing_feasibility=None,
    pin_report=None,
    diff_pair_report: DiffPairSkewReport | None = None,
    autoroute_result=None,
    resource_allocation_result=None,
    footprint_preview_result=None,
) -> DeliveryArtifactResult:
    artifacts = collect_artifact_manifest(out_dir)
    planned_artifacts = artifact_paths(artifacts) | {"decision_manifest.json"}
    process_report = generate_design_process_report(
        cfg,
        run_id=run_id,
        board=board,
        coverage=coverage,
        module_graph_result=module_graph_result,
        module_compatibility_result=module_compatibility_result,
        routing_feasibility=routing_feasibility,
        manufacturing_report=manufacturing_report,
        diff_pair_report=diff_pair_report,
        autoroute_result=autoroute_result,
        prior_manifest=prior_manifest,
        generated_artifacts=planned_artifacts,
    )
    process_report.write(out_dir / "design_process_report.txt")
    coverage.write(out_dir / "testpoint_report.txt")
    readiness = generate_readiness_report(
        coverage,
        run_id=run_id,
        module_library_preflight=module_library_preflight_result,
        module_selection=module_selection,
        module_graph_result=module_graph_result,
        module_compatibility_result=module_compatibility_result,
        module_placement_result=module_placement_result,
        module_instantiation_result=module_instantiation_result,
        routing_feasibility=routing_feasibility,
        pin_mapping_result=pin_report.result if pin_report is not None else None,
        manufacturing_report=manufacturing_report,
        diff_pair_report=diff_pair_report,
        process_report=process_report,
        resource_allocation_result=resource_allocation_result,
        footprint_preview_result=footprint_preview_result,
    )
    readiness.write(out_dir / "readiness_report.txt")
    artifacts = collect_artifact_manifest(out_dir)
    manifest = write_decision_manifest(
        out_dir / "decision_manifest.json",
        run_id=run_id,
        cfg=cfg,
        coverage=coverage,
        readiness_report=readiness,
        process_report=process_report,
        module_selection=module_selection,
        module_graph_result=module_graph_result,
        module_compatibility_result=module_compatibility_result,
        routing_feasibility=routing_feasibility,
        autoroute_result=autoroute_result,
        prior_manifest=prior_manifest,
        artifacts=artifacts,
    )
    return DeliveryArtifactResult(
        process_report=process_report,
        readiness_report=readiness,
        manifest=manifest,
        artifacts=artifacts,
    )
