#!/usr/bin/env python3
"""Create a reviewed native KiCad regression baseline from summary.json."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_probe_router.native_findings import finding_fingerprint, group_findings

STALE_FINGERPRINT_EXIT = 3


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        summary = _load_json(args.summary)
    except FileNotFoundError as exc:
        print(f"summary file not found: {exc.filename}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"failed to parse summary JSON: {exc}", file=sys.stderr)
        return 2

    if not isinstance(summary, dict):
        print("summary JSON must contain an object", file=sys.stderr)
        return 2
    findings = summary.get("findings")
    if not isinstance(findings, list):
        print("summary JSON must contain a findings list", file=sys.stderr)
        return 2

    normalized_findings, warnings = _normalize_findings(findings)
    grouped = group_findings(normalized_findings)
    payload = {
        "schema_version": 1,
        "generated_from": {
            "summary": str(args.summary),
            "repo": args.repo,
            "workflow": args.workflow,
            "job": args.job,
            "artifact": args.artifact,
            "report_subdir": args.report_subdir,
            "commit_sha": args.commit_sha,
            "run_url": args.run_url,
            "generated_at_utc": args.generated_at_utc or _utc_now(),
        },
        "kicad_version": str(summary.get("kicad_version", "")),
        "kicad_major": summary.get("kicad_major"),
        "counts": {
            "finding_total": _count(
                summary,
                "finding_total",
                "finding_count",
                len(normalized_findings),
            ),
            "group_total": _count(
                summary,
                "group_total",
                "grouped_finding_count",
                len(grouped),
            ),
        },
        "policy": {
            "blocks_new_findings": True,
            "allows_existing_findings": True,
            "category_key_fields": ["source", "severity", "type", "message"],
            "fingerprint_fields": ["source", "severity", "type", "message", "item", "path"],
            "fingerprint_format": "sha1-lowercase-hex-40",
        },
        "findings": normalized_findings,
    }
    _write_json(args.output, payload)
    for warning in warnings:
        print(warning, file=sys.stderr)
    return STALE_FINGERPRINT_EXIT if warnings else 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True, help="native summary.json")
    parser.add_argument("--output", type=Path, required=True, help="baseline JSON to write")
    parser.add_argument("--repo", default="", help="GitHub repo, for example owner/name")
    parser.add_argument("--workflow", default="ci.yml")
    parser.add_argument("--job", default="native-kicad")
    parser.add_argument("--artifact", default="native-validation-reports")
    parser.add_argument("--report-subdir", default="validation/reports/audio")
    parser.add_argument("--commit-sha", default="")
    parser.add_argument("--run-url", default="")
    parser.add_argument("--generated-at-utc", default="")
    return parser


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_findings(rows: list[Any]) -> tuple[list[dict[str, Any]], list[str]]:
    findings = []
    warnings = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            warnings.append(f"warning: skipped non-object finding at index {index}")
            continue
        normalized = {
            "source": _string_field(row, "source"),
            "severity": _string_field(row, "severity"),
            "type": _string_field(row, "type"),
            "message": _string_field(row, "message"),
            "item": _string_field(row, "item"),
            "path": _string_field(row, "path"),
        }
        fingerprint = finding_fingerprint(normalized)
        existing = row.get("fingerprint")
        if existing and existing != fingerprint:
            warnings.append(
                "warning: stale fingerprint at index "
                f"{index}; expected {fingerprint}, got {existing}"
            )
        normalized["fingerprint"] = fingerprint
        findings.append(normalized)
    return findings, warnings


def _string_field(row: dict[str, Any], field: str) -> str:
    value = row.get(field, "")
    return "" if value is None else str(value)


def _count(summary: dict[str, Any], primary: str, fallback: str, default: int) -> int:
    value = summary.get(primary)
    if value is None:
        value = summary.get(fallback, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
