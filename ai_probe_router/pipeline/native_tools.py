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
)
from ..verification.native_validation_runner import (
    NativeValidationOptions,
    NativeValidationRun,
)
from ..verification.native_validation_runner import (
    run_native_validation as run_shared_native_validation,
)
from ..verification.report import CoverageReport


@dataclass
class NativeValidationResult:
    drc: CheckResult | None = None
    erc: CheckResult | None = None
    parity: CheckResult | None = None
    netlist: CheckResult | None = None
    summary: dict | None = None
    report_dir: Path | None = None
    return_code: int = 0


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
    project_root = _common_project_root(pcb_path, schematic_path, output_dir)
    run = run_shared_native_validation(
        NativeValidationOptions(
            project_root=project_root,
            schematic=_relative_existing_path(schematic_path, project_root),
            pcb=_relative_existing_path(pcb_path, project_root),
            report_dir=output_dir / "native_validation",
            strict=False,
            require_kicad=False,
            require_kicad_major=None,
            enable_erc=schematic_path is not None and schematic_path.exists(),
            enable_drc=pcb_path is not None and pcb_path.exists(),
            enable_parity=pcb_path is not None and pcb_path.exists(),
        )
    )
    return _native_result_from_run(run)


def _common_project_root(
    pcb_path: Path | None,
    schematic_path: Path | None,
    output_dir: Path,
) -> Path:
    for path in (pcb_path, schematic_path):
        if path is not None and path.exists():
            return path.resolve().parent
    return output_dir.resolve()


def _relative_existing_path(path: Path | None, project_root: Path) -> str | None:
    if path is None or not path.exists():
        return None
    try:
        return path.resolve().relative_to(project_root).as_posix()
    except ValueError:
        return str(path.resolve())


def _native_result_from_run(run: NativeValidationRun) -> NativeValidationResult:
    checks = run.summary.get("checks", {}) if isinstance(run.summary, dict) else {}
    return NativeValidationResult(
        drc=_check_result("drc", checks.get("drc"), run.findings),
        erc=_check_result("erc", checks.get("erc"), run.findings),
        parity=_check_result("parity", checks.get("parity"), run.findings),
        netlist=_check_result("netlist", checks.get("netlist"), run.findings),
        summary=run.summary,
        report_dir=run.report_dir,
        return_code=run.return_code,
    )


# KiCad DRC/ERC severities that must not block manufacturing signoff. Library
# bookkeeping findings (lib_footprint_mismatch / lib_footprint_issues) and
# user-acknowledged items are reported as warnings, not manufacturability
# defects, so they are recorded in the native report but never raised on.
# A finding without an explicit severity is treated as blocking.
_NON_BLOCKING_SEVERITIES = frozenset({"warning", "exclusion", "ignore"})


def _is_blocking_finding(finding: dict) -> bool:
    severity = str(finding.get("severity", "")).strip().lower()
    return severity not in _NON_BLOCKING_SEVERITIES


def _check_result(
    key: str,
    check: dict | None,
    findings: list[dict],
) -> CheckResult | None:
    if check is None:
        return None
    relevant = [finding for finding in findings if finding.get("source") == key]
    blocking = [finding for finding in relevant if _is_blocking_finding(finding)]
    exit_code = check.get("exit_code")
    json_exists = bool(check.get("json_exists"))
    if key == "netlist":
        ok = exit_code == 0
    elif key in {"erc", "drc"} and not json_exists:
        ok = None
    else:
        # Only error-severity findings block signoff; warnings are advisory.
        ok = len(blocking) == 0
    error = ""
    if ok is None:
        error = "native KiCad report was not produced"
    elif ok is False:
        error = f"{len(blocking)} violation(s)"
    return CheckResult(ok=ok, violations=blocking, error=error)


def apply_native_validation(
    coverage: CoverageReport,
    result: NativeValidationResult,
    cfg: ProjectConfig | None = None,
    *,
    defer_failures: bool = False,
) -> None:
    if result.drc is not None:
        coverage.drc_ok = result.drc.ok
        coverage.drc_violations = len(result.drc.violations)
        _record_native_validation_result(
            coverage, result.drc, "DRC", cfg, defer_failures=defer_failures
        )
    if result.erc is not None:
        coverage.erc_ok = result.erc.ok
        coverage.erc_violations = len(result.erc.violations)
        _record_native_validation_result(
            coverage, result.erc, "ERC", cfg, defer_failures=defer_failures
        )
    if result.parity is not None and result.parity.ok is False:
        _record_native_validation_result(
            coverage,
            result.parity,
            "Schematic parity",
            cfg,
            defer_failures=defer_failures,
        )


def _record_native_validation_result(
    coverage: CoverageReport,
    result: CheckResult,
    label: str,
    cfg: ProjectConfig | None,
    *,
    defer_failures: bool,
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
    if cfg is not None and cfg.process_controls.strict_signoff and not defer_failures:
        raise RuntimeError(message)


def run_manufacturing_exports(
    cfg: ProjectConfig,
    coverage: CoverageReport,
    pcb_path: Path,
    output_dir: Path,
    *,
    defer_failures: bool = False,
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
            defer_failures=defer_failures,
        ),
        _record_manufacturing_export(
            cfg,
            coverage,
            export_drill(pcb_path, output_dir),
            "Drill",
            "Drill files exported",
            defer_failures=defer_failures,
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
            defer_failures=defer_failures,
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
    *,
    defer_failures: bool = False,
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
    ) and not defer_failures:
        raise RuntimeError(message)
    return ManufacturingExportStatus(
        label=label,
        ok=result.ok,
        note=message,
        output_path=output_path,
    )
