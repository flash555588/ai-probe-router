#!/usr/bin/env python3
"""Compare native KiCad findings against a reviewed baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ai_probe_router.verification.native_validation_runner import (
    compare_findings_to_baseline,
)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    summary = _load_json(args.current)
    findings = summary.get("findings") if isinstance(summary, dict) else None
    if not isinstance(findings, list):
        result = {
            "enabled": True,
            "status": "summary_invalid",
            "baseline_path": str(args.baseline),
            "counts": {
                "current_total": 0,
                "baseline_total": 0,
                "existing": 0,
                "new_regressions": 0,
                "resolved": 0,
                "increased": 0,
            },
            "new_regressions": [],
            "resolved": [],
            "increased": [],
            "notes": ["summary JSON must contain a findings list"],
        }
        _write_json(args.output, result)
        return 3

    result = compare_findings_to_baseline(
        findings=findings,
        baseline_path=args.baseline,
        enabled=True,
    )
    _write_json(args.output, result)
    if result["status"] in {"baseline_missing", "baseline_invalid", "summary_invalid"}:
        return 3
    return 1 if result["status"] == "failed" else 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", type=Path, required=True, help="native summary.json")
    parser.add_argument("--baseline", type=Path, required=True, help="reviewed baseline JSON")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("validation/reports/regression-result.json"),
        help="regression result JSON path",
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


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
