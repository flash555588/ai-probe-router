#!/usr/bin/env python3
"""Generate grouped native KiCad finding reports from summary.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ai_probe_router.verification.native_validation_runner import (
    group_findings,
    grouped_findings_markdown,
)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    summary = _load_json(args.summary)
    findings = summary.get("findings") if isinstance(summary, dict) else None
    if not isinstance(findings, list):
        raise SystemExit("summary JSON must contain a findings list")
    grouped = group_findings([finding for finding in findings if isinstance(finding, dict)])
    _write_json(args.json_output, grouped)
    _write_text(args.markdown_output, grouped_findings_markdown(grouped))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True, help="native summary.json")
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("validation/reports/grouped-findings.json"),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path("validation/reports/grouped-findings.md"),
    )
    return parser


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"failed to read {path}: {exc}") from exc


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
