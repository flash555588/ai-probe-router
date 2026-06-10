#!/usr/bin/env python3
"""Review a native KiCad baseline for schema and evidence quality."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_probe_router.native_findings import finding_fingerprint

SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
SEMVERISH_RE = re.compile(r"\d+\.\d+(?:\.\d+)?")
FINGERPRINT_RE = re.compile(r"^[0-9a-f]{40}$")
GARBLED_RE = re.compile(r"(?:\ufffd|\\x[0-9a-fA-F]{2})")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    issues = _review(args.baseline, args.summary, args.check_commit)
    if args.markdown_output:
        _write_report(args.markdown_output, issues)
    for issue in issues:
        print(f"{issue['level']}: {issue['message']}", file=sys.stderr)
    return 1 if any(issue["level"] == "error" for issue in issues) else 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True, help="baseline JSON")
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="optional source summary.json for KiCad version consistency checks",
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help="optional markdown review report path",
    )
    parser.add_argument(
        "--check-commit",
        action="store_true",
        help="verify generated_from.commit_sha exists in the current git repository",
    )
    return parser


def _review(baseline_path: Path, summary_path: Path | None, check_commit: bool) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    baseline = _read_json(baseline_path, issues, "baseline")
    if not isinstance(baseline, dict):
        return issues

    findings = baseline.get("findings")
    if not isinstance(findings, list):
        issues.append(_error("baseline JSON must contain a findings list"))
        findings = []
    if not findings:
        issues.append(_warning("baseline findings array is empty"))

    generated_from = baseline.get("generated_from")
    if not isinstance(generated_from, dict):
        issues.append(_error("generated_from metadata is required"))
        generated_from = {}
    _required_metadata(generated_from, issues)
    _validate_generated_at(generated_from.get("generated_at_utc"), issues)
    _validate_commit(generated_from.get("commit_sha"), check_commit, issues)

    kicad_version = str(baseline.get("kicad_version", ""))
    if not kicad_version:
        issues.append(_error("kicad_version is required"))
    elif not SEMVERISH_RE.search(kicad_version):
        issues.append(_error(f"kicad_version does not look versioned: {kicad_version}"))

    if summary_path is not None:
        summary = _read_json(summary_path, issues, "summary")
        if isinstance(summary, dict):
            summary_version = str(summary.get("kicad_version", ""))
            if summary_version and kicad_version and summary_version != kicad_version:
                issues.append(
                    _error(
                        "baseline kicad_version does not match summary "
                        f"({kicad_version} != {summary_version})"
                    )
                )

    _validate_counts(baseline, findings, issues)
    _validate_findings(findings, issues)
    _add_distribution_notes(findings, issues)
    return issues


def _read_json(path: Path, issues: list[dict[str, str]], label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        issues.append(_error(f"{label} file not found: {path}"))
    except json.JSONDecodeError as exc:
        issues.append(_error(f"{label} JSON is invalid: {exc}"))
    return None


def _required_metadata(metadata: dict[str, Any], issues: list[dict[str, str]]) -> None:
    required = [
        "repo",
        "workflow",
        "job",
        "artifact",
        "report_subdir",
        "commit_sha",
        "run_url",
        "generated_at_utc",
    ]
    for field in required:
        if not str(metadata.get(field, "")).strip():
            issues.append(_error(f"generated_from.{field} is required"))


def _validate_generated_at(value: Any, issues: list[dict[str, str]]) -> None:
    text = str(value or "")
    if not text:
        return
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        issues.append(_error(f"generated_from.generated_at_utc is not ISO 8601: {text}"))


def _validate_commit(value: Any, check_commit: bool, issues: list[dict[str, str]]) -> None:
    sha = str(value or "")
    if not sha:
        return
    if not SHA_RE.match(sha):
        issues.append(_error(f"generated_from.commit_sha is not a hex commit SHA: {sha}"))
        return
    if check_commit:
        result = subprocess.run(
            ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            issues.append(_error(f"generated_from.commit_sha does not exist locally: {sha}"))


def _validate_counts(
    baseline: dict[str, Any],
    findings: list[Any],
    issues: list[dict[str, str]],
) -> None:
    counts = baseline.get("counts")
    if not isinstance(counts, dict):
        issues.append(_error("counts metadata is required"))
        return
    if int(counts.get("finding_total", -1)) != len(findings):
        issues.append(_error("counts.finding_total does not match findings length"))
    groups = {
        (
            str(row.get("source", "")),
            str(row.get("severity", "")),
            str(row.get("type", "")),
            str(row.get("message", "")),
        )
        for row in findings
        if isinstance(row, dict)
    }
    if int(counts.get("group_total", -1)) != len(groups):
        issues.append(_error("counts.group_total does not match grouped category count"))


def _validate_findings(findings: list[Any], issues: list[dict[str, str]]) -> None:
    category_counts: Counter[tuple[str, str, str, str]] = Counter()
    for index, row in enumerate(findings):
        if not isinstance(row, dict):
            issues.append(_error(f"finding {index} must be an object"))
            continue
        missing = [
            field
            for field in ("source", "severity", "type", "message", "item", "path", "fingerprint")
            if field not in row
        ]
        if missing:
            issues.append(_error(f"finding {index} missing fields: {', '.join(missing)}"))
        fingerprint = str(row.get("fingerprint", ""))
        if not FINGERPRINT_RE.match(fingerprint):
            issues.append(_error(f"finding {index} fingerprint must be 40 lowercase hex chars"))
        else:
            expected = finding_fingerprint(row)
            if fingerprint != expected:
                issues.append(_error(f"finding {index} fingerprint is stale"))
        message = str(row.get("message", ""))
        if len(message.strip()) < 10:
            issues.append(_warning(f"finding {index} message is very short"))
        if GARBLED_RE.search(message):
            issues.append(_warning(f"finding {index} message may contain garbled text"))
        category_counts[
            (
                str(row.get("source", "")),
                str(row.get("severity", "")),
                str(row.get("type", "")),
                message,
            )
        ] += 1
    for category, count in sorted(category_counts.items()):
        if count > 1:
            issues.append(
                _info(
                    "category appears multiple times as expected for baseline counts: "
                    f"{category[0]}/{category[1]}/{category[2]} ({count})"
                )
            )


def _add_distribution_notes(findings: list[Any], issues: list[dict[str, str]]) -> None:
    distribution: Counter[str] = Counter()
    for row in findings:
        if isinstance(row, dict):
            distribution[str(row.get("severity", "")) or "none"] += 1
    if distribution:
        formatted = ", ".join(f"{severity}={count}" for severity, count in sorted(distribution.items()))
        issues.append(_info(f"severity distribution: {formatted}"))


def _write_report(path: Path, issues: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Native KiCad Baseline Review",
        "",
        "| Level | Message |",
        "|---|---|",
    ]
    for issue in issues:
        lines.append(f"| {issue['level']} | {issue['message']} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _error(message: str) -> dict[str, str]:
    return {"level": "error", "message": message}


def _warning(message: str) -> dict[str, str]:
    return {"level": "warning", "message": message}


def _info(message: str) -> dict[str, str]:
    return {"level": "info", "message": message}


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
