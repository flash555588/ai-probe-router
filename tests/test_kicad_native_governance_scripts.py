"""Tests for native KiCad regression and grouping helpers."""

from __future__ import annotations

import json
from pathlib import Path

from ai_probe_router.verification.native_validation_runner import finding_fingerprint
from scripts import (
    kicad_native_baseline_create,
    kicad_native_baseline_review,
    kicad_native_group_findings,
    kicad_native_regression_gate,
)


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
    assert payload["comparison"]["new_regressions"][0]["absolute_delta"] == 1
    assert payload["comparison"]["increased"][0]["baseline_count"] == 1
    assert payload["comparison"]["increased"][0]["current_count"] == 2


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
    assert payload["counts"]["unchanged"] == 1
    assert payload["counts"]["reduced"] == 0
    assert payload["comparison"]["resolved"][0]["current_count"] == 0


def test_regression_gate_reports_reduced_categories(tmp_path: Path):
    current = tmp_path / "summary.json"
    baseline = tmp_path / "baseline.json"
    output = tmp_path / "regression-result.json"
    baseline.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "findings": [
                    _finding("erc", "unconnected_pin", "Pin is not connected", "U1"),
                    _finding("erc", "unconnected_pin", "Pin is not connected", "U2"),
                    _finding("erc", "unconnected_pin", "Pin is not connected", "U3"),
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
                ]
            }
        ),
        encoding="utf-8",
    )

    result = kicad_native_regression_gate.main(
        ["--current", str(current), "--baseline", str(baseline), "--output", str(output)]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["counts"]["reduced"] == 1
    assert payload["comparison"]["reduced"][0]["absolute_delta"] == -2
    assert payload["comparison"]["reduced"][0]["percentage_delta"] == -66.7


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
    markdown = grouped_md.read_text(encoding="utf-8")
    assert "Native Validation Findings by Class" in markdown
    assert "Severity Distribution" in markdown
    assert "| **Total** | **3** | **3** |" in markdown


def test_baseline_create_recomputes_stale_fingerprints(tmp_path: Path):
    summary = tmp_path / "summary.json"
    output = tmp_path / "native-baseline.json"
    row = _finding("erc", "unconnected_pin", "Pin is not connected", "U1")
    row["fingerprint"] = "stale"
    summary.write_text(
        json.dumps(
            {
                "kicad_version": "9.0.2",
                "kicad_major": 9,
                "finding_count": 1,
                "grouped_finding_count": 1,
                "findings": [row],
            }
        ),
        encoding="utf-8",
    )

    result = kicad_native_baseline_create.main(
        [
            "--summary",
            str(summary),
            "--output",
            str(output),
            "--repo",
            "flash555588/ai-probe-router",
            "--commit-sha",
            "cf83241",
            "--run-url",
            "https://github.com/flash555588/ai-probe-router/actions/runs/1",
            "--generated-at-utc",
            "2026-06-10T03:15:22Z",
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result == 3
    assert payload["counts"] == {"finding_total": 1, "group_total": 1}
    assert payload["policy"]["fingerprint_format"] == "sha1-lowercase-hex-40"
    assert payload["findings"][0]["fingerprint"] == finding_fingerprint(payload["findings"][0])


def test_baseline_review_rejects_stale_fingerprint_and_bad_counts(tmp_path: Path):
    baseline = tmp_path / "native-baseline.json"
    report = tmp_path / "review.md"
    row = _finding("erc", "unconnected_pin", "Pin is not connected", "U1")
    row["fingerprint"] = "0" * 40
    baseline.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_from": _metadata(),
                "kicad_version": "9.0.2",
                "counts": {"finding_total": 2, "group_total": 1},
                "findings": [row],
            }
        ),
        encoding="utf-8",
    )

    result = kicad_native_baseline_review.main(
        ["--baseline", str(baseline), "--markdown-output", str(report)]
    )

    text = report.read_text(encoding="utf-8")
    assert result == 1
    assert "counts.finding_total does not match findings length" in text
    assert "fingerprint is stale" in text


def test_baseline_review_accepts_create_output(tmp_path: Path):
    summary = tmp_path / "summary.json"
    baseline = tmp_path / "native-baseline.json"
    row = _finding("drc", "clearance", "Clearance violation", "J1")
    summary.write_text(
        json.dumps(
            {
                "kicad_version": "9.0.2",
                "kicad_major": 9,
                "findings": [row],
            }
        ),
        encoding="utf-8",
    )
    assert (
        kicad_native_baseline_create.main(
            [
                "--summary",
                str(summary),
                "--output",
                str(baseline),
                "--repo",
                "flash555588/ai-probe-router",
                "--commit-sha",
                "cf83241",
                "--run-url",
                "https://github.com/flash555588/ai-probe-router/actions/runs/1",
                "--generated-at-utc",
                "2026-06-10T03:15:22Z",
            ]
        )
        == 0
    )

    assert (
        kicad_native_baseline_review.main(
            ["--baseline", str(baseline), "--summary", str(summary)]
        )
        == 0
    )


def test_committed_audio_baseline_passes_against_itself(tmp_path: Path):
    baseline = (
        Path(__file__).parent.parent
        / "examples"
        / "audio_player_project"
        / "ci"
        / "native-baseline.kicad9.json"
    )
    output = tmp_path / "regression-result.json"

    result = kicad_native_regression_gate.main(
        ["--current", str(baseline), "--baseline", str(baseline), "--output", str(output)]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["status"] == "passed"
    assert payload["counts"]["new_regressions"] == 0
    assert payload["counts"]["increased"] == 0
    assert payload["counts"]["unchanged"] == 8


def _metadata() -> dict[str, str]:
    return {
        "repo": "flash555588/ai-probe-router",
        "workflow": "ci.yml",
        "job": "native-kicad",
        "artifact": "native-validation-reports",
        "report_subdir": "validation/reports/audio",
        "commit_sha": "cf83241",
        "run_url": "https://github.com/flash555588/ai-probe-router/actions/runs/1",
        "generated_at_utc": "2026-06-10T03:15:22Z",
    }


def _finding(source: str, issue_type: str, message: str, item: str) -> dict[str, str]:
    finding = {
        "source": source,
        "severity": "error",
        "type": issue_type,
        "message": message,
        "item": item,
        "path": "main.kicad_sch",
    }
    finding["fingerprint"] = finding_fingerprint(finding)
    return finding
