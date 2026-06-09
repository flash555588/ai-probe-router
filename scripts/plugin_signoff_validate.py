#!/usr/bin/env python3
"""Validate manual KiCad plugin/GUI signoff evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REQUIRED_TRUE_FIELDS = {
    "plugin_shell_no_3d_opened",
    "report_tabs_rendered",
    "three_d_view_checked",
    "action_plugin_visible",
    "action_plugin_generates_output",
    "temporary_config_selects_nontrivial_nets",
    "error_dialog_captures_cli_failure",
}

_REQUIRED_TEXT_FIELDS = {
    "evidence_link",
    "kicad_version",
    "os",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "evidence",
        nargs="?",
        type=Path,
        default=Path("plugin_signoff.json"),
        help="JSON evidence file produced during manual KiCad/plugin signoff",
    )
    parser.add_argument(
        "--require-signoff",
        action="store_true",
        help="fail when the evidence file is missing",
    )
    args = parser.parse_args(argv)

    if not args.evidence.is_file():
        print(f"plugin signoff evidence not found: {args.evidence}")
        return 1 if args.require_signoff else 0

    try:
        raw = json.loads(args.evidence.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"plugin signoff evidence is not valid JSON: {exc}")
        return 1
    if not isinstance(raw, dict):
        print("plugin signoff evidence must be a JSON object")
        return 1

    errors = _validate_evidence(raw)
    if errors:
        for error in errors:
            print(error)
        return 1

    print(
        "plugin signoff evidence accepted: "
        f"KiCad {raw['kicad_version']} on {raw['os']}"
    )
    return 0


def _validate_evidence(raw: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in sorted(_REQUIRED_TEXT_FIELDS):
        if not str(raw.get(field, "")).strip():
            errors.append(f"{field} is required")
    for field in sorted(_REQUIRED_TRUE_FIELDS):
        if raw.get(field) is not True:
            errors.append(f"{field} must be true")
    notes = raw.get("notes", [])
    if notes is not None and not isinstance(notes, list):
        errors.append("notes must be a list when provided")
    return errors


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
