"""Footprint preview report formatting."""

from __future__ import annotations

import json
from pathlib import Path

from ..models.footprint_preview import FootprintPreviewResult


def generate_footprint_preview_text(result: FootprintPreviewResult) -> str:
    lines = ["Module Footprint Preview Report", "=" * 40, ""]
    lines.append(f"Planned footprints: {len(result.planned_footprints)}")
    lines.append("")

    for fp in result.planned_footprints:
        lines.append(
            f"  {fp.reference} ({fp.footprint}) @ ({fp.x_mm:.2f}, {fp.y_mm:.2f}) "
            f"rot={fp.rotation_deg} side={fp.side} module={fp.module_name}"
        )

    if result.issues:
        lines.append("")
        lines.append("Issues:")
        for issue in result.issues:
            prefix = issue.severity.value.upper()
            ref = f" [{issue.reference}]" if issue.reference else ""
            lines.append(f"  {prefix} {issue.code}{ref}: {issue.message}")

    lines.append("")
    if result.ok:
        lines.append("Result: OK")
    else:
        lines.append("Result: BLOCKED")
    return "\n".join(lines)


def generate_footprint_preview_json(result: FootprintPreviewResult) -> str:
    data = {
        "schema_version": 1,
        "ok": result.ok,
        "has_warnings": result.has_warnings,
        "planned_footprints": [
            {
                "module_name": fp.module_name,
                "reference": fp.reference,
                "footprint": fp.footprint,
                "x_mm": fp.x_mm,
                "y_mm": fp.y_mm,
                "rotation_deg": fp.rotation_deg,
                "side": fp.side,
                "role": fp.role,
            }
            for fp in result.planned_footprints
        ],
        "issues": [
            {
                "severity": issue.severity.value,
                "code": issue.code,
                "message": issue.message,
                "module_name": issue.module_name,
                "reference": issue.reference,
            }
            for issue in result.issues
        ],
    }
    return json.dumps(data, indent=2)


def write_footprint_preview_report(
    result: FootprintPreviewResult,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    text_path = output_dir / "footprint_preview_report.txt"
    json_path = output_dir / "footprint_preview_report.json"
    text_path.write_text(generate_footprint_preview_text(result), encoding="utf-8")
    json_path.write_text(generate_footprint_preview_json(result), encoding="utf-8")
