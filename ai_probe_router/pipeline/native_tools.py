"""Native KiCad validation and manufacturing export pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import ProjectConfig
from ..eda_adapters.kicad.cli_runner import (
    CheckResult,
    export_drill,
    export_gerbers,
    export_pos,
    run_drc,
    run_erc,
)
from ..verification.report import CoverageReport


@dataclass
class NativeValidationResult:
    drc: CheckResult | None = None
    erc: CheckResult | None = None


@dataclass(frozen=True)
class ManufacturingExportStatus:
    label: str
    ok: bool | None
    note: str
    output_path: str = ""


def run_native_validation(
    pcb_path: Path | None,
    schematic_path: Path | None,
    output_dir: Path,
) -> NativeValidationResult:
    result = NativeValidationResult()
    if pcb_path is not None and pcb_path.exists():
        result.drc = run_drc(pcb_path, output_dir)
    if schematic_path is not None and schematic_path.exists():
        result.erc = run_erc(schematic_path, output_dir)
    return result


def apply_native_validation(
    coverage: CoverageReport,
    result: NativeValidationResult,
    cfg: ProjectConfig | None = None,
) -> None:
    if result.drc is not None:
        coverage.drc_ok = result.drc.ok
        coverage.drc_violations = len(result.drc.violations)
        _record_native_validation_result(coverage, result.drc, "DRC", cfg)
    if result.erc is not None:
        coverage.erc_ok = result.erc.ok
        coverage.erc_violations = len(result.erc.violations)
        _record_native_validation_result(coverage, result.erc, "ERC", cfg)


def _record_native_validation_result(
    coverage: CoverageReport,
    result: CheckResult,
    label: str,
    cfg: ProjectConfig | None,
) -> None:
    if result.ok is True:
        return

    if result.ok is None:
        reason = result.error or "native KiCad validation skipped"
        message = f"{label} validation skipped: {reason}"
    else:
        reason = result.error or f"{len(result.violations)} violation(s)"
        message = f"{label} validation failed: {reason}"
    coverage.notes.append(message)
    if cfg is not None and cfg.process_controls.strict_signoff:
        raise RuntimeError(message)


def run_manufacturing_exports(
    cfg: ProjectConfig,
    coverage: CoverageReport,
    pcb_path: Path,
    output_dir: Path,
) -> list[ManufacturingExportStatus]:
    if not pcb_path.exists():
        return []

    output_dir.mkdir(exist_ok=True)
    statuses = [
        _record_manufacturing_export(
            cfg,
            coverage,
            export_gerbers(pcb_path, output_dir),
            "Gerber",
            "Gerber files exported",
        ),
        _record_manufacturing_export(
            cfg,
            coverage,
            export_drill(pcb_path, output_dir),
            "Drill",
            "Drill files exported",
        ),
    ]
    pos_file = output_dir / "placement.csv"
    statuses.append(
        _record_manufacturing_export(
            cfg,
            coverage,
            export_pos(pcb_path, pos_file),
            "Pick&Place",
            "Pick&Place file exported",
            output_path=str(pos_file),
        )
    )
    return statuses


def _record_manufacturing_export(
    cfg: ProjectConfig,
    coverage: CoverageReport,
    result: CheckResult,
    label: str,
    success_note: str,
    output_path: str = "",
) -> ManufacturingExportStatus:
    if result.ok:
        coverage.notes.append(success_note)
        return ManufacturingExportStatus(
            label=label,
            ok=result.ok,
            note=success_note,
            output_path=output_path,
        )

    reason = result.error or "unknown error"
    message = f"{label} export failed: {reason}"
    coverage.notes.append(message)
    if (
        cfg.process_controls.strict_signoff
        or cfg.process_controls.require_manufacturing_exports
    ):
        raise RuntimeError(message)
    return ManufacturingExportStatus(
        label=label,
        ok=result.ok,
        note=message,
        output_path=output_path,
    )
