"""Shared native KiCad validation runner and evidence contract."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ai_probe_router.eda_adapters.kicad.cli_runner import find_kicad_cli
from ai_probe_router.eda_adapters.kicad.sch_health import healthcheck_schematic


@dataclass(frozen=True)
class NativeValidationOptions:
    project_root: Path = Path(".")
    schematic: str | None = "main.kicad_sch"
    pcb: str | None = "main.kicad_pcb"
    build_dir: Path | None = None
    report_dir: Path | None = None
    strict: bool = False
    require_kicad: bool = False
    require_kicad_major: int | None = 9
    enable_erc: bool = True
    enable_drc: bool = True
    enable_parity: bool = True
    baseline: Path | None = None
    block_new_regressions: bool = False
    kicad_cli: str | None = None


@dataclass(frozen=True)
class NativeCommand:
    key: str
    label: str
    command: list[str]
    json_path: Path | None = None


@dataclass(frozen=True)
class NativeCheckResult:
    key: str
    label: str
    ran: bool
    exit_code: int | None
    json_path: str
    json_exists: bool
    stdout: str
    stderr: str
    finding_count: int


@dataclass(frozen=True)
class NativeValidationRun:
    return_code: int
    summary: dict[str, Any]
    report_dir: Path
    findings: list[dict[str, Any]]
    grouped_findings: list[dict[str, Any]]
    regression_result: dict[str, Any]
    checks: list[NativeCheckResult] = field(default_factory=list)


def run_native_validation(
    options: NativeValidationOptions,
    *,
    echo: bool = False,
) -> NativeValidationRun:
    """Run KiCad validation and write a deterministic evidence directory."""

    emit = print if echo else None
    project_root = options.project_root.resolve()
    report_dir = _resolve_report_dir(project_root, options.report_dir, options.build_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    _prepare_report_dirs(report_dir)

    schematic = project_root / options.schematic if options.schematic else None
    pcb = project_root / options.pcb if options.pcb else None
    kicad_cli = options.kicad_cli or find_kicad_cli()
    if kicad_cli is None:
        return _missing_tool_run(options, project_root, report_dir, emit)

    notes: list[str] = []
    health_ok = True
    if schematic is not None and schematic.is_file():
        health = healthcheck_schematic(schematic)
        health_ok = health.ok
        for line in health.to_lines():
            if line:
                _emit(emit, line)
    elif options.enable_erc:
        health_ok = False
        notes.append(f"schematic file not found: {schematic}")

    commands = _commands(
        kicad_cli=kicad_cli,
        schematic=schematic if schematic is not None and schematic.is_file() else None,
        pcb=pcb if pcb is not None and pcb.is_file() else None,
        report_dir=report_dir,
        enable_erc=options.enable_erc,
        enable_drc=options.enable_drc,
        enable_parity=options.enable_parity,
    )

    version = _run_version(commands[0], project_root, report_dir, emit)
    version_major = _kicad_major(version)
    if (
        options.require_kicad_major is not None
        and version_major is not None
        and version_major != options.require_kicad_major
    ):
        notes.append(
            f"kicad-cli major version {version_major} does not match "
            f"required major version {options.require_kicad_major}"
        )

    results: list[NativeCheckResult] = []
    findings: list[dict[str, Any]] = []
    for command in commands[1:]:
        result = _run_native_command(command, project_root, report_dir, emit)
        results.append(result)
        findings.extend(_extract_findings(command.key, project_root, command.json_path))

    if options.enable_drc and options.enable_parity:
        parity_result = _write_parity_report(report_dir, project_root, results)
        results.append(parity_result)
        findings.extend(
            _extract_findings(
                "parity",
                project_root,
                report_dir / "parity" / "parity.json",
            )
        )

    grouped = group_findings(findings)
    regression_result = compare_findings_to_baseline(
        findings=findings,
        baseline_path=options.baseline.resolve() if options.baseline is not None else None,
        enabled=options.block_new_regressions,
    )
    if regression_result["enabled"]:
        _write_json(report_dir / "regression-result.json", regression_result)
    _write_json(report_dir / "grouped-findings.json", grouped)
    _write_text(report_dir / "grouped-findings.md", grouped_findings_markdown(grouped))

    status = _status(
        health_ok=health_ok,
        version_major=version_major,
        required_major=options.require_kicad_major,
        results=results,
        findings=findings,
        strict=options.strict,
        regression_result=regression_result,
    )
    summary = _summary(
        status=status,
        project_root=project_root,
        report_dir=report_dir,
        kicad_version=version,
        health_ok=health_ok,
        version_major=version_major,
        required_major=options.require_kicad_major,
        results=results,
        findings=findings,
        regression_result=regression_result,
        notes=notes,
    )
    _write_json(report_dir / "summary.json", summary)
    _write_text(report_dir / "project-file-list.txt", _project_file_list(project_root))
    _write_text(report_dir / "file-list.txt", _report_file_list(report_dir))
    _write_json(report_dir / "artifact_manifest.json", _artifact_manifest(report_dir))

    return_code = _return_code(
        options=options,
        health_ok=health_ok,
        version_major=version_major,
        results=results,
        findings=findings,
        regression_result=regression_result,
    )
    return NativeValidationRun(
        return_code=return_code,
        summary=summary,
        report_dir=report_dir,
        findings=findings,
        grouped_findings=grouped,
        regression_result=regression_result,
        checks=results,
    )


def _resolve_report_dir(
    project_root: Path,
    report_dir: Path | None,
    build_dir: Path | None,
) -> Path:
    if report_dir is not None:
        return report_dir.resolve()
    if build_dir is None:
        return project_root / "build" / "kicad"
    if build_dir.is_absolute():
        return build_dir
    return project_root / build_dir


def _missing_tool_run(
    options: NativeValidationOptions,
    project_root: Path,
    report_dir: Path,
    emit: Callable[[str], None] | None,
) -> NativeValidationRun:
    message = "kicad-cli not installed; skipping native KiCad validation"
    _emit(emit, message)
    grouped: list[dict[str, Any]] = []
    regression_result = compare_findings_to_baseline(
        findings=[],
        baseline_path=options.baseline.resolve() if options.baseline is not None else None,
        enabled=options.block_new_regressions,
    )
    if regression_result["enabled"]:
        _write_json(report_dir / "regression-result.json", regression_result)
    summary = {
        "status": "tool_missing" if options.require_kicad else "skipped",
        "kicad_version": "",
        "kicad_major": None,
        "required_kicad_major": options.require_kicad_major,
        "project_root": str(project_root),
        "report_dir": str(report_dir),
        "schematic_health_ok": None,
        "checks": {},
        "findings": [],
        "finding_count": 0,
        "grouped_finding_count": 0,
        "regression_gate": {
            "enabled": regression_result["enabled"],
            "status": regression_result["status"],
            "new_regressions": regression_result["counts"]["new_regressions"],
            "resolved": regression_result["counts"]["resolved"],
            "increased": regression_result["counts"]["increased"],
        },
        "notes": [message],
    }
    _write_text(report_dir / "kicad-version.txt", "")
    _write_text(report_dir / "version.stdout.log", "")
    _write_text(report_dir / "version.stderr.log", "")
    _write_json(report_dir / "grouped-findings.json", grouped)
    _write_text(report_dir / "grouped-findings.md", grouped_findings_markdown(grouped))
    _write_json(report_dir / "summary.json", summary)
    _write_text(report_dir / "project-file-list.txt", _project_file_list(project_root))
    _write_text(report_dir / "file-list.txt", _report_file_list(report_dir))
    _write_json(report_dir / "artifact_manifest.json", _artifact_manifest(report_dir))
    return NativeValidationRun(
        return_code=1 if options.require_kicad else 0,
        summary=summary,
        report_dir=report_dir,
        findings=[],
        grouped_findings=grouped,
        regression_result=regression_result,
        checks=[],
    )


def _prepare_report_dirs(report_dir: Path) -> None:
    for name in ("netlist", "erc", "drc", "parity"):
        (report_dir / name).mkdir(parents=True, exist_ok=True)


def _commands(
    *,
    kicad_cli: str,
    schematic: Path | None,
    pcb: Path | None,
    report_dir: Path,
    enable_erc: bool,
    enable_drc: bool,
    enable_parity: bool,
) -> list[NativeCommand]:
    commands = [NativeCommand("version", "version", [kicad_cli, "version"])]
    if schematic is not None:
        commands.append(
            NativeCommand(
                "netlist",
                "schematic netlist export",
                [
                    kicad_cli,
                    "sch",
                    "export",
                    "netlist",
                    "--output",
                    str(report_dir / "netlist" / "main.net"),
                    "--format",
                    "kicadsexpr",
                    str(schematic),
                ],
                report_dir / "netlist" / "main.net",
            )
        )
    if schematic is not None and enable_erc:
        commands.append(
            NativeCommand(
                "erc",
                "schematic ERC",
                [
                    kicad_cli,
                    "sch",
                    "erc",
                    "--output",
                    str(report_dir / "erc" / "erc.json"),
                    "--format",
                    "json",
                    "--exit-code-violations",
                    str(schematic),
                ],
                report_dir / "erc" / "erc.json",
            )
        )
    if pcb is not None and enable_drc:
        drc_command = [
            kicad_cli,
            "pcb",
            "drc",
            "--output",
            str(report_dir / "drc" / "drc.json"),
            "--format",
            "json",
        ]
        if enable_parity:
            drc_command.append("--schematic-parity")
        drc_command.extend(["--exit-code-violations", str(pcb)])
        commands.append(
            NativeCommand("drc", "PCB DRC", drc_command, report_dir / "drc" / "drc.json")
        )
    return commands


def _run_version(
    command: NativeCommand,
    cwd: Path,
    report_dir: Path,
    emit: Callable[[str], None] | None,
) -> str:
    _emit(emit, "+ " + " ".join(command.command))
    completed = subprocess.run(
        command.command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (completed.stdout or completed.stderr or "").strip()
    _write_text(report_dir / "kicad-version.txt", output + ("\n" if output else ""))
    _write_text(report_dir / "version.stdout.log", completed.stdout)
    _write_text(report_dir / "version.stderr.log", completed.stderr)
    if completed.returncode != 0:
        _emit(emit, f"{command.label} failed with exit code {completed.returncode}")
    elif output:
        _emit(emit, output)
    return output.splitlines()[0] if output else ""


def _run_native_command(
    command: NativeCommand,
    cwd: Path,
    report_dir: Path,
    emit: Callable[[str], None] | None,
) -> NativeCheckResult:
    _emit(emit, "+ " + " ".join(command.command))
    stdout_path = report_dir / command.key / "stdout.log"
    stderr_path = report_dir / command.key / "stderr.log"
    completed = subprocess.run(
        command.command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    _write_text(stdout_path, completed.stdout)
    _write_text(stderr_path, completed.stderr)
    if completed.stdout:
        _emit(emit, completed.stdout.rstrip())
    if completed.stderr:
        _emit(emit, completed.stderr.rstrip())
    if completed.returncode != 0:
        _emit(emit, f"{command.label} failed with exit code {completed.returncode}")
    return NativeCheckResult(
        key=command.key,
        label=command.label,
        ran=True,
        exit_code=completed.returncode,
        json_path=_relative(command.json_path, report_dir) if command.json_path else "",
        json_exists=command.json_path.is_file() if command.json_path else False,
        stdout=_relative(stdout_path, report_dir),
        stderr=_relative(stderr_path, report_dir),
        finding_count=len(_extract_findings(command.key, cwd, command.json_path)),
    )


def _write_parity_report(
    report_dir: Path,
    project_root: Path,
    results: list[NativeCheckResult],
) -> NativeCheckResult:
    parity_json = report_dir / "parity" / "parity.json"
    stdout_path = report_dir / "parity" / "stdout.log"
    stderr_path = report_dir / "parity" / "stderr.log"
    parity_rows = _parity_rows(report_dir / "drc" / "drc.json")
    _write_json(parity_json, {"violations": parity_rows})
    _write_text(
        stdout_path,
        "schematic parity is included in the PCB DRC command via --schematic-parity\n",
    )
    _write_text(stderr_path, "")
    drc_result = next((result for result in results if result.key == "drc"), None)
    return NativeCheckResult(
        key="parity",
        label="schematic parity",
        ran=drc_result is not None and drc_result.ran,
        exit_code=(
            drc_result.exit_code
            if parity_rows and drc_result is not None and drc_result.exit_code != 0
            else 0
        ),
        json_path=_relative(parity_json, report_dir),
        json_exists=True,
        stdout=_relative(stdout_path, report_dir),
        stderr=_relative(stderr_path, report_dir),
        finding_count=len(_extract_findings("parity", project_root, parity_json)),
    )


def _parity_rows(drc_json: Path) -> list[Any]:
    if not drc_json.is_file():
        return []
    try:
        raw = json.loads(drc_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    direct_rows: list[Any] = []
    if isinstance(raw, dict):
        for key in ("schematic_parity", "schematicParity", "parity"):
            value = raw.get(key)
            if isinstance(value, list):
                direct_rows.extend(value)
    return direct_rows or [row for row in _finding_rows(raw) if _is_parity_row(row)]


def _extract_findings(
    source: str,
    project_root: Path,
    path: Path | None,
) -> list[dict[str, Any]]:
    if path is None or not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    rows = _finding_rows(raw)
    if source == "drc":
        rows = [row for row in rows if not _is_parity_row(row)]
    findings = []
    for row in rows:
        finding = normalize_finding(source, row, project_root)
        finding["fingerprint"] = finding_fingerprint(finding)
        findings.append(finding)
    return findings


def _finding_rows(raw: Any) -> list[Any]:
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, dict):
        return []
    rows: list[Any] = []
    for key in ("violations", "errors", "warnings"):
        value = raw.get(key)
        if isinstance(value, list):
            rows.extend(value)
    return rows


def _is_parity_row(row: Any) -> bool:
    if not isinstance(row, dict):
        return False
    haystack = " ".join(
        str(row.get(key, ""))
        for key in ("code", "type", "category", "message", "description", "text")
    ).lower()
    return "parity" in haystack


def normalize_finding(source: str, row: Any, project_root: Path) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {
            "source": source,
            "severity": "unknown",
            "type": "unknown",
            "message": _normalize_text(str(row)),
            "item": "",
            "path": "",
        }
    message = _normalize_text(
        str(
            row.get("message")
            or row.get("description")
            or row.get("text")
            or row.get("errorMessage")
            or ""
        )
    )
    item = _normalize_text(
        str(row.get("item") or row.get("ref") or row.get("pin") or row.get("net") or "")
    )
    raw_path = str(row.get("file") or row.get("path") or row.get("sheet") or "")
    return {
        "source": source,
        "severity": str(row.get("severity") or row.get("type") or "unknown"),
        "type": str(row.get("code") or row.get("type") or row.get("category") or "unknown"),
        "message": message,
        "item": item,
        "path": _normalize_path(raw_path, project_root),
    }


def finding_fingerprint(finding: dict[str, Any]) -> str:
    parts = [
        finding.get("source", ""),
        finding.get("severity", ""),
        finding.get("type", ""),
        finding.get("message", ""),
        finding.get("item", ""),
        finding.get("path", ""),
    ]
    raw = "\x1f".join(str(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def group_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for finding in findings:
        key = (
            str(finding.get("source", "")),
            str(finding.get("severity", "")),
            str(finding.get("type", "")),
            str(finding.get("message", "")),
        )
        group = grouped.setdefault(
            key,
            {
                "source": key[0],
                "severity": key[1],
                "type": key[2],
                "message": key[3],
                "count": 0,
                "examples": [],
            },
        )
        group["count"] += 1
        if len(group["examples"]) < 3:
            group["examples"].append(finding)
    return sorted(
        grouped.values(),
        key=lambda row: (-int(row["count"]), row["source"], row["type"], row["message"]),
    )


def grouped_findings_markdown(grouped: list[dict[str, Any]]) -> str:
    lines = [
        "# Native Validation Findings by Class",
        "",
        "| Rank | Source | Severity | Type | Count | Message | Example |",
        "|---:|---|---|---|---:|---|---|",
    ]
    for index, group in enumerate(grouped, start=1):
        example = group.get("examples", [{}])[0]
        example_text = str(example.get("item") or example.get("path") or "")
        lines.append(
            f"| {index} | {group['source']} | {group['severity']} | "
            f"{group['type']} | {group['count']} | {group['message']} | {example_text} |"
        )
    lines.append("")
    return "\n".join(lines)


def compare_findings_to_baseline(
    *,
    findings: list[dict[str, Any]],
    baseline_path: Path | None,
    enabled: bool,
) -> dict[str, Any]:
    current_categories = _categories_by_key(findings)
    if not enabled:
        return {
            "enabled": False,
            "status": "disabled",
            "baseline_path": str(baseline_path) if baseline_path is not None else "",
            "counts": {
                "current_total": len(findings),
                "baseline_total": 0,
                "existing": 0,
                "new_regressions": 0,
                "resolved": 0,
                "increased": 0,
            },
            "new_regressions": [],
            "resolved": [],
            "increased": [],
            "notes": [],
        }
    if baseline_path is None:
        return _regression_error(
            "baseline_missing",
            "native validation regression gate requires --baseline",
            len(findings),
            "",
        )
    if not baseline_path.is_file():
        return _regression_error(
            "baseline_missing",
            f"baseline file not found: {baseline_path}",
            len(findings),
            str(baseline_path),
        )
    try:
        baseline_payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _regression_error(
            "baseline_invalid",
            f"baseline file is not valid JSON: {exc}",
            len(findings),
            str(baseline_path),
        )
    baseline_findings = (
        baseline_payload.get("findings")
        if isinstance(baseline_payload, dict)
        else None
    )
    if not isinstance(baseline_findings, list):
        return _regression_error(
            "baseline_invalid",
            "baseline JSON must contain a findings list",
            len(findings),
            str(baseline_path),
        )

    baseline_categories = _categories_by_key(
        [finding for finding in baseline_findings if isinstance(finding, dict)]
    )
    current_keys = set(current_categories)
    baseline_keys = set(baseline_categories)
    new_keys = sorted(current_keys - baseline_keys)
    resolved_keys = sorted(baseline_keys - current_keys)
    increased_keys = sorted(
        key
        for key in current_keys & baseline_keys
        if current_categories[key]["count"] > baseline_categories[key]["count"]
    )
    failed = bool(new_keys or increased_keys)
    return {
        "enabled": True,
        "status": "failed" if failed else "passed",
        "baseline_path": str(baseline_path),
        "counts": {
            "current_total": len(findings),
            "baseline_total": len(baseline_findings),
            "existing": len(current_keys & baseline_keys),
            "new_regressions": len(new_keys),
            "resolved": len(resolved_keys),
            "increased": len(increased_keys),
        },
        "new_regressions": [current_categories[key] for key in new_keys],
        "resolved": [baseline_categories[key] for key in resolved_keys],
        "increased": [
            {
                **current_categories[key],
                "baseline_count": baseline_categories[key]["count"],
            }
            for key in increased_keys
        ],
        "notes": [],
    }


def _categories_by_key(findings: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    categories: dict[str, dict[str, Any]] = {}
    for finding in findings:
        key = _category_key(finding)
        category = categories.setdefault(
            key,
            {
                "key": key,
                "source": str(finding.get("source", "")),
                "severity": str(finding.get("severity", "")),
                "type": str(finding.get("type", "")),
                "message": str(finding.get("message", "")),
                "count": 0,
                "examples": [],
            },
        )
        category["count"] += 1
        if len(category["examples"]) < 3:
            category["examples"].append(finding)
    return categories


def _category_key(finding: dict[str, Any]) -> str:
    parts = [
        finding.get("source", ""),
        finding.get("severity", ""),
        finding.get("type", ""),
        finding.get("message", ""),
    ]
    return hashlib.sha1("\x1f".join(str(part) for part in parts).encode("utf-8")).hexdigest()


def _regression_error(
    status: str,
    note: str,
    current_total: int,
    baseline_path: str,
) -> dict[str, Any]:
    return {
        "enabled": True,
        "status": status,
        "baseline_path": baseline_path,
        "counts": {
            "current_total": current_total,
            "baseline_total": 0,
            "existing": 0,
            "new_regressions": 0,
            "resolved": 0,
            "increased": 0,
        },
        "new_regressions": [],
        "resolved": [],
        "increased": [],
        "notes": [note],
    }


def _summary(
    *,
    status: str,
    project_root: Path,
    report_dir: Path,
    kicad_version: str,
    health_ok: bool,
    version_major: int | None,
    required_major: int | None,
    results: list[NativeCheckResult],
    findings: list[dict[str, Any]],
    regression_result: dict[str, Any],
    notes: list[str],
) -> dict[str, Any]:
    return {
        "status": status,
        "kicad_version": kicad_version,
        "kicad_major": version_major,
        "required_kicad_major": required_major,
        "project_root": str(project_root),
        "report_dir": str(report_dir),
        "schematic_health_ok": health_ok,
        "checks": {
            result.key: {
                "ran": result.ran,
                "exit_code": result.exit_code,
                "json_path": result.json_path,
                "json_exists": result.json_exists,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "finding_count": result.finding_count,
            }
            for result in results
        },
        "findings": findings,
        "finding_count": len(findings),
        "grouped_finding_count": len(group_findings(findings)),
        "regression_gate": {
            "enabled": regression_result["enabled"],
            "status": regression_result["status"],
            "new_regressions": regression_result["counts"]["new_regressions"],
            "resolved": regression_result["counts"]["resolved"],
            "increased": regression_result["counts"]["increased"],
        },
        "notes": notes,
    }


# DRC/ERC severities that are advisory and must not fail native validation.
# Library bookkeeping (lib_footprint_mismatch / lib_footprint_issues) and
# user-acknowledged items are reported as warnings, not manufacturability
# defects. A finding without an explicit severity is treated as blocking.
_NON_BLOCKING_SEVERITIES = frozenset({"warning", "exclusion", "ignore"})


def _blocking_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocking = []
    for finding in findings:
        severity = str(finding.get("severity", "")).strip().lower()
        if severity not in _NON_BLOCKING_SEVERITIES:
            blocking.append(finding)
    return blocking


def _status(
    *,
    health_ok: bool,
    version_major: int | None,
    required_major: int | None,
    results: list[NativeCheckResult],
    findings: list[dict[str, Any]],
    strict: bool,
    regression_result: dict[str, Any],
) -> str:
    if not health_ok:
        return "infrastructure_failed"
    if required_major is not None and version_major is not None and version_major != required_major:
        return "infrastructure_failed"
    if _has_native_runtime_failure(results) or _baseline_failed(regression_result):
        return "infrastructure_failed"
    if regression_result["enabled"]:
        if (
            regression_result["counts"]["new_regressions"] > 0
            or regression_result["counts"]["increased"] > 0
        ):
            return "regression_failed"
        return "passed"
    # Only error-severity findings fail validation; warnings remain advisory and
    # are still recorded in the grouped report. `strict` is retained for API
    # stability but warnings no longer block under it.
    if _blocking_findings(findings):
        return "findings_failed"
    return "passed"


def _return_code(
    *,
    options: NativeValidationOptions,
    health_ok: bool,
    version_major: int | None,
    results: list[NativeCheckResult],
    findings: list[dict[str, Any]],
    regression_result: dict[str, Any],
) -> int:
    if not health_ok:
        return 2
    if (
        options.require_kicad_major is not None
        and version_major is not None
        and version_major != options.require_kicad_major
    ):
        return 2
    if _has_native_runtime_failure(results):
        return 2
    if _baseline_failed(regression_result):
        return 3
    if options.block_new_regressions:
        return 1 if regression_result["status"] == "failed" else 0
    if _blocking_findings(findings):
        return 1
    return 0


def _has_native_runtime_failure(results: list[NativeCheckResult]) -> bool:
    for result in results:
        if result.key == "netlist" and result.exit_code not in (0, None):
            return True
        if result.key in {"erc", "drc"}:
            if result.json_path and not result.json_exists:
                return True
            # Exit code 5 is kicad-cli's documented --exit-code-violations
            # signal ("violations present"), not a tool crash. The violations
            # may be warnings or schematic-parity issues counted under a
            # different check, so this command can legitimately report zero
            # findings of its own. Only other non-zero codes mean a real crash.
            if result.exit_code not in (0, None, 5) and result.finding_count == 0:
                return True
    return False


def _baseline_failed(regression_result: dict[str, Any]) -> bool:
    return regression_result["enabled"] and regression_result["status"] in {
        "baseline_missing",
        "baseline_invalid",
    }


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def _normalize_path(path: str, project_root: Path) -> str:
    if not path:
        return ""
    raw_path = Path(path)
    candidate = raw_path if raw_path.is_absolute() else project_root / raw_path
    try:
        return candidate.resolve().relative_to(project_root).as_posix()
    except (OSError, ValueError):
        return path


def _kicad_major(version: str) -> int | None:
    for token in version.replace("-", " ").split():
        head = token.split(".", 1)[0]
        if head.isdigit():
            return int(head)
    return None


def _project_file_list(project_root: Path) -> str:
    patterns = ("*.kicad_pro", "*.kicad_sch", "*.kicad_pcb")
    files: list[Path] = []
    for pattern in patterns:
        files.extend(project_root.rglob(pattern))
    return "\n".join(str(path.resolve()) for path in sorted(files)) + "\n"


def _report_file_list(report_dir: Path) -> str:
    return "\n".join(
        _relative(path, report_dir)
        for path in sorted(report_dir.rglob("*"))
        if path.is_file()
    ) + "\n"


def _artifact_manifest(report_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(report_dir.rglob("*")):
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        data = path.read_bytes()
        rows.append(
            {
                "path": _relative(path, report_dir),
                "size_bytes": len(data),
                "sha1": hashlib.sha1(data).hexdigest(),
            }
        )
    return rows


def _relative(path: Path | None, root: Path) -> str:
    if path is None:
        return ""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text or "", encoding="utf-8")


def _emit(emit: Callable[[str], None] | None, message: str) -> None:
    if emit is not None:
        emit(message)
