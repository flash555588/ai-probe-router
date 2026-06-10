"""Decision manifest writer for reproducible planning runs."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from ai_probe_router import __version__
from ai_probe_router.routing.freerouting_bridge import find_freerouting
from ai_probe_router.subprocess_utils import run_text_tool


def read_prior_manifest(path: str | Path) -> dict[str, Any] | None:
    manifest_path = Path(path)
    if not manifest_path.is_file():
        return None
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def collect_artifact_manifest(out_dir: str | Path) -> list[dict[str, Any]]:
    root = Path(out_dir)
    if not root.exists():
        return []
    artifacts: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel == "decision_manifest.json":
            continue
        data = path.read_bytes()
        artifacts.append({
            "path": rel,
            "size_bytes": len(data),
            "sha1": hashlib.sha1(data).hexdigest(),
        })
    return artifacts


def artifact_paths(artifacts: list[dict[str, Any]]) -> set[str]:
    return {str(artifact.get("path", "")) for artifact in artifacts}


def write_decision_manifest(
    path: str | Path,
    *,
    run_id: str,
    cfg,
    coverage,
    readiness_report,
    process_report,
    module_selection=None,
    module_graph_result=None,
    module_compatibility_result=None,
    routing_feasibility=None,
    autoroute_result=None,
    prior_manifest: dict[str, Any] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    manifest = {
        "manifest_version": 1,
        "run_id": run_id,
        "tool_versions": _tool_versions(),
        "native_tools": _native_tools(),
        "project": {
            "schema_version": cfg.schema_version,
            "eda_tool": cfg.eda_tool,
            "board_file": cfg.board_file,
            "schematic_file": cfg.schematic_file,
        },
        "readiness": {
            "verdict": readiness_report.verdict,
            "blockers": len(readiness_report.blockers),
            "warnings": len(readiness_report.warnings),
            "infos": len(readiness_report.infos),
        },
        "coverage": {
            "requested": coverage.total_nets_requested,
            "covered": coverage.covered,
            "missing": coverage.missing,
            "coverage_pct": coverage.coverage_pct,
            "routing_ok": coverage.routing_ok,
            "drc_ok": coverage.drc_ok,
            "erc_ok": coverage.erc_ok,
            "notes": list(coverage.notes),
        },
        "modules": _modules(module_graph_result),
        "module_selection": _module_selection(module_selection),
        "module_compatibility": _module_compatibility(module_compatibility_result),
        "routing": _routing(routing_feasibility, autoroute_result),
        "process": _process(process_report),
        "waivers": _waivers(cfg),
        "artifacts": artifacts or [],
        "change_summary": _change_summary(prior_manifest, run_id, module_graph_result),
    }
    manifest_path = Path(path)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _tool_versions() -> dict[str, str]:
    return {
        "ai_probe_router": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }


def _native_tools() -> dict[str, dict[str, str | bool | None]]:
    freerouting_path = find_freerouting()
    return {
        "kicad_cli": _executable_tool("kicad-cli", ["kicad-cli", "version"]),
        "java": _executable_tool("java", ["java", "-version"], stderr_version=True),
        "freerouting": _freerouting_tool(freerouting_path),
    }


def _tool_presence(name: str) -> dict[str, str | bool | None]:
    path = shutil.which(name)
    return {
        "available": path is not None,
        "path": path or "",
        "version": "",
        "version_error": "",
    }


def _executable_tool(
    name: str,
    version_cmd: list[str],
    *,
    stderr_version: bool = False,
) -> dict[str, str | bool | None]:
    info = _tool_presence(name)
    if not info["available"]:
        return info
    version, error = _probe_version(version_cmd, stderr_version=stderr_version)
    info["version"] = version
    info["version_error"] = error
    return info


def _freerouting_tool(path: str | None) -> dict[str, str | bool | None]:
    if path is None:
        return {
            "available": False,
            "path": "",
            "version": "",
            "version_error": "",
            "kind": "",
            "java_available": shutil.which("java") is not None,
        }
    info: dict[str, str | bool | None] = {
        "available": True,
        "path": path,
        "version": "",
        "version_error": "",
        "kind": "jar" if path.lower().endswith(".jar") else "executable",
        "java_available": shutil.which("java") is not None,
    }
    if info["kind"] == "jar":
        java = shutil.which("java")
        if java is None:
            info["version_error"] = "java not found in PATH"
            return info
        cmd = [java, "-jar", path, "--version"]
    else:
        cmd = [path, "--version"]
    version, error = _probe_version(cmd)
    info["version"] = version
    info["version_error"] = error
    return info


def _probe_version(
    cmd: list[str],
    *,
    stderr_version: bool = False,
) -> tuple[str, str]:
    try:
        proc = run_text_tool(
            cmd,
            capture_output=True,
            timeout=5,
        )
    except (FileNotFoundError, OSError) as exc:
        return "", str(exc)
    except subprocess.TimeoutExpired:
        return "", "version probe timed out"

    output = proc.stderr if stderr_version else proc.stdout
    if not output.strip() and stderr_version:
        output = proc.stdout
    if not output.strip():
        output = proc.stderr
    first_line = output.strip().splitlines()[0] if output.strip() else ""
    if proc.returncode != 0 and not first_line:
        return "", f"version probe exited with code {proc.returncode}"
    if proc.returncode != 0:
        return first_line, f"version probe exited with code {proc.returncode}"
    return first_line, ""


def _modules(module_graph_result) -> list[dict[str, Any]]:
    if module_graph_result is None:
        return []
    rows = []
    for instance in module_graph_result.graph.instances:
        rows.append({
            "module_id": instance.instance_id,
            "name": instance.name,
            "type": instance.module_type,
            "required": instance.required,
            "implementation": instance.selected_implementation,
            "implementation_version": instance.selected_implementation_version,
            "definition_version": instance.selected_definition_version,
            "area_mm2": instance.area_mm2,
            "target_nets": instance.target_nets,
            "generated_nets": instance.generated_nets,
            "rails": instance.rails,
            "voltage_domains": instance.voltage_domains,
            "review_required": instance.review_required,
        })
    return rows


def _module_selection(module_selection) -> dict[str, Any]:
    if module_selection is None:
        return {"selected": [], "errors": [], "warnings": []}
    return {
        "selected": [
            {
                "name": selected.module.name,
                "type": selected.module.type,
                "implementation": selected.implementation.name,
                "reasons": selected.reasons,
                "rejected": selected.rejected,
            }
            for selected in module_selection.selected
        ],
        "errors": list(module_selection.errors),
        "warnings": list(module_selection.warnings),
    }


def _module_compatibility(result) -> dict[str, Any]:
    if result is None:
        return {"rows": 0, "errors": [], "warnings": []}
    return {
        "rows": len(result.rows),
        "errors": list(result.errors),
        "warnings": list(result.warnings),
    }


def _routing(routing_feasibility, autoroute_result) -> dict[str, Any]:
    corridors = []
    if routing_feasibility is not None:
        corridors = [
            {
                "source": corridor.source_id,
                "target": corridor.target_id,
                "ok": corridor.ok,
                "length_mm": corridor.length_mm,
                "total_cost": corridor.total_cost,
                "message": corridor.message,
            }
            for corridor in routing_feasibility.corridors
        ]
    autoroute = None
    if autoroute_result is not None:
        autoroute = {
            "ok": autoroute_result.ok,
            "dsn_path": autoroute_result.dsn_path,
            "ses_path": autoroute_result.ses_path,
            "error": autoroute_result.error,
            "duration_sec": autoroute_result.duration_sec,
        }
    return {"corridors": corridors, "autorouter": autoroute}


def _process(process_report) -> dict[str, Any]:
    if process_report is None:
        return {"issues": []}
    return {
        "open_errors": len(process_report.open_errors),
        "open_warnings": len(process_report.open_warnings),
        "waived": len(process_report.waived_issues),
        "issues": [
            {
                "severity": issue.severity,
                "source": issue.source,
                "issue_id": issue.issue_id,
                "status": issue.status,
                "waiver_id": issue.waiver_id,
                "message": issue.message,
                "recommendation": issue.recommendation,
            }
            for issue in process_report.issues
        ],
    }


def _waivers(cfg) -> list[dict[str, str]]:
    return [
        {
            "waiver_id": waiver.waiver_id,
            "source": waiver.source,
            "issue_id": waiver.issue_id,
            "owner": waiver.owner,
            "reason": waiver.reason,
            "expires_on": waiver.expires_on,
        }
        for waiver in cfg.process_controls.waivers
    ]


def _change_summary(
    prior_manifest: dict[str, Any] | None,
    run_id: str,
    module_graph_result,
) -> dict[str, Any]:
    if not prior_manifest:
        return {"status": "no_prior_manifest", "previous_run_id": ""}
    previous_modules = {
        str(row.get("name", "")) for row in prior_manifest.get("modules", [])
        if isinstance(row, dict)
    }
    current_modules = {
        instance.name for instance in module_graph_result.graph.instances
    } if module_graph_result is not None else set()
    return {
        "status": "unchanged" if prior_manifest.get("run_id") == run_id else "changed",
        "previous_run_id": str(prior_manifest.get("run_id", "")),
        "run_id_changed": prior_manifest.get("run_id") != run_id,
        "added_modules": sorted(current_modules - previous_modules),
        "removed_modules": sorted(previous_modules - current_modules),
    }
