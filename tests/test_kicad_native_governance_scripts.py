"""Tests for native KiCad regression and grouping helpers."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import kicad_native_group_findings, kicad_native_regression_gate


def test_regression_gate_blocks_new_category_and_increased_count(tmp_path: Path):
    current = tmp_path / "summary.json"
    baseline = tmp_path / "baseline.json"
    output = tmp_path / "regression-result.json"
    baseline.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "findings": [
                    _finding("erc", "unconnected_pin", "Pin is not connected", "U1"),
                ],
            }
        ),
        encoding="utf-8",
    )
    current.write_text(
        json.dumps(
            {
                "findings": [
                    _finding("erc", "unconnected_pin", "Pin is not connected", "U1"),
                    _finding("erc", "unconnected_pin", "Pin is not connected", "U2"),
                    _finding("drc", "clearance", "Clearance violation", "J1"),
                ]
            }
        ),
        encoding="utf-8",
    )

    result = kicad_native_regression_gate.main(
        ["--current", str(current), "--baseline", str(baseline), "--output", str(output)]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result == 1
    assert payload["status"] == "failed"
    assert payload["counts"]["new_regressions"] == 1
    assert payload["counts"]["increased"] == 1


def test_regression_gate_passes_same_or_lower_counts(tmp_path: Path):
    current = tmp_path / "summary.json"
    baseline = tmp_path / "baseline.json"
    output = tmp_path / "regression-result.json"
    current_findings = [_finding("erc", "unconnected_pin", "Pin is not connected", "U1")]
    current.write_text(json.dumps({"findings": current_findings}), encoding="utf-8")
    baseline.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "findings": [
                    *current_findings,
                    _finding("drc", "clearance", "Clearance violation", "J1"),
                ],
            }
        ),
        encoding="utf-8",
    )

    result = kicad_native_regression_gate.main(
        ["--current", str(current), "--baseline", str(baseline), "--output", str(output)]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["status"] == "passed"
    assert payload["counts"]["new_regressions"] == 0
    assert payload["counts"]["resolved"] == 1


def test_group_findings_script_writes_json_and_markdown(tmp_path: Path):
    summary = tmp_path / "summary.json"
    grouped_json = tmp_path / "grouped-findings.json"
    grouped_md = tmp_path / "grouped-findings.md"
    summary.write_text(
        json.dumps(
            {
                "findings": [
                    _finding("erc", "unconnected_pin", "Pin is not connected", "U1"),
                    _finding("erc", "unconnected_pin", "Pin is not connected", "U2"),
                    _finding("drc", "clearance", "Clearance violation", "J1"),
                ]
            }
        ),
        encoding="utf-8",
    )

    result = kicad_native_group_findings.main(
        [
            "--summary",
            str(summary),
            "--json-output",
            str(grouped_json),
            "--markdown-output",
            str(grouped_md),
        ]
    )

    grouped = json.loads(grouped_json.read_text(encoding="utf-8"))
    assert result == 0
    assert grouped[0]["source"] == "erc"
    assert grouped[0]["count"] == 2
    assert "Native Validation Findings by Class" in grouped_md.read_text(encoding="utf-8")


def _finding(source: str, issue_type: str, message: str, item: str) -> dict[str, str]:
    return {
        "source": source,
        "severity": "error",
        "type": issue_type,
        "message": message,
        "item": item,
        "path": "main.kicad_sch",
        "fingerprint": f"{source}-{issue_type}-{item}",
    }
