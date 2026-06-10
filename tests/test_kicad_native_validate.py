"""Tests for optional native KiCad validation wrapper."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from ai_probe_router.verification import native_validation_runner
from scripts import kicad_native_validate


def test_native_validate_skips_when_kicad_cli_missing(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(native_validation_runner, "find_kicad_cli", lambda: None)

    result = kicad_native_validate.main([str(tmp_path)])

    report_dir = tmp_path / "build" / "kicad"
    summary = json.loads((report_dir / "summary.json").read_text(encoding="utf-8"))
    assert result == 0
    assert summary["status"] == "skipped"
    assert summary["notes"] == ["kicad-cli not installed; skipping native KiCad validation"]
    assert (report_dir / "file-list.txt").is_file()
    assert (report_dir / "grouped-findings.json").is_file()
    assert "kicad-cli not installed; skipping" in capsys.readouterr().out


def test_native_validate_requires_kicad_when_requested(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(native_validation_runner, "find_kicad_cli", lambda: None)

    assert kicad_native_validate.main([str(tmp_path), "--require-kicad"]) == 1
    summary = json.loads((tmp_path / "build" / "kicad" / "summary.json").read_text())
    assert summary["status"] == "tool_missing"


def test_native_validate_writes_evidence_and_absolute_kicad_commands(
    tmp_path: Path,
    monkeypatch,
):
    schematic, pcb = _write_project(tmp_path)
    commands: list[tuple[list[str], dict[str, Any]]] = []

    monkeypatch.setattr(native_validation_runner, "find_kicad_cli", lambda: "kicad-cli")
    monkeypatch.setattr(
        native_validation_runner.subprocess,
        "run",
        _fake_kicad_run(commands, erc_exit=0, drc_exit=0, severity="warning"),
    )

    report_dir = tmp_path / "native-reports"
    result = kicad_native_validate.main([str(tmp_path), "--report-dir", str(report_dir)])

    summary = json.loads((report_dir / "summary.json").read_text(encoding="utf-8"))
    grouped = json.loads((report_dir / "grouped-findings.json").read_text(encoding="utf-8"))
    assert result == 0
    assert commands[0][0][1:] == ["version"]
    assert commands[1][0][1:4] == ["sch", "export", "netlist"]
    assert commands[2][0][1:3] == ["sch", "erc"]
    assert commands[3][0][1:3] == ["pcb", "drc"]
    assert commands[1][0][-1] == str(schematic.resolve())
    assert commands[2][0][-1] == str(schematic.resolve())
    assert commands[3][0][-1] == str(pcb.resolve())
    assert "--exit-code-violations" in commands[2][0]
    assert "--exit-code-violations" in commands[3][0]
    assert "--schematic-parity" in commands[3][0]
    assert all(kwargs["cwd"] == tmp_path.resolve() for _, kwargs in commands)
    assert all(kwargs["check"] is False for _, kwargs in commands)
    assert all(kwargs["capture_output"] is True for _, kwargs in commands)
    assert all(kwargs["text"] is True for _, kwargs in commands)

    assert (report_dir / "kicad-version.txt").read_text(encoding="utf-8") == "9.0.2\n"
    assert (report_dir / "netlist" / "main.net").read_text(
        encoding="utf-8"
    ) == "(exported_netlist)\n"
    assert (report_dir / "erc" / "stdout.log").read_text(encoding="utf-8") == "erc stdout\n"
    assert (report_dir / "erc" / "stderr.log").read_text(encoding="utf-8") == "erc stderr\n"
    assert (report_dir / "drc" / "drc.json").is_file()
    assert (report_dir / "parity" / "parity.json").is_file()
    assert (report_dir / "grouped-findings.md").is_file()
    assert "summary.json" in (report_dir / "file-list.txt").read_text(encoding="utf-8")
    assert str(schematic.resolve()) in (report_dir / "project-file-list.txt").read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "passed"
    assert summary["kicad_version"] == "9.0.2"
    assert summary["project_root"] == str(tmp_path.resolve())
    assert summary["report_dir"] == str(report_dir.resolve())
    assert summary["checks"]["erc"]["json_path"] == "erc/erc.json"
    assert summary["checks"]["erc"]["json_exists"] is True
    assert summary["checks"]["erc"]["finding_count"] == 1
    assert summary["checks"]["drc"]["finding_count"] == 1
    assert summary["checks"]["parity"]["finding_count"] == 1
    assert summary["finding_count"] == 3
    assert summary["findings"][0]["path"] == "main.kicad_sch"
    assert summary["regression_gate"]["enabled"] is False
    assert [row["source"] for row in grouped] == ["drc", "erc", "parity"]


def test_native_validate_runs_all_commands_before_reporting_failure(
    tmp_path: Path,
    monkeypatch,
):
    _write_project(tmp_path)
    commands: list[tuple[list[str], dict[str, Any]]] = []

    monkeypatch.setattr(native_validation_runner, "find_kicad_cli", lambda: "kicad-cli")
    monkeypatch.setattr(
        native_validation_runner.subprocess,
        "run",
        _fake_kicad_run(commands, erc_exit=5, drc_exit=0),
    )

    result = kicad_native_validate.main([str(tmp_path)])

    assert result == 1
    assert len(commands) == 4
    assert commands[-1][0][1:3] == ["pcb", "drc"]
    summary = json.loads((tmp_path / "build" / "kicad" / "summary.json").read_text())
    assert summary["status"] == "findings_failed"
    assert summary["checks"]["erc"]["exit_code"] == 5
    assert summary["checks"]["drc"]["exit_code"] == 0


def test_native_validate_warning_findings_do_not_fail(tmp_path: Path, monkeypatch):
    """Warning-severity findings (and the exit-code-5 violations signal) must
    not fail native validation, even under --strict."""
    _write_project(tmp_path)
    commands: list[tuple[list[str], dict[str, Any]]] = []

    monkeypatch.setattr(native_validation_runner, "find_kicad_cli", lambda: "kicad-cli")
    monkeypatch.setattr(
        native_validation_runner.subprocess,
        "run",
        _fake_kicad_run(commands, erc_exit=5, drc_exit=5, severity="warning"),
    )

    result = kicad_native_validate.main([str(tmp_path), "--strict"])

    summary = json.loads((tmp_path / "build" / "kicad" / "summary.json").read_text())
    assert result == 0
    assert summary["status"] == "passed"
    assert summary["finding_count"] == 3


def test_native_validate_blocks_new_regressions_against_baseline(
    tmp_path: Path,
    monkeypatch,
):
    _write_project(tmp_path)
    commands: list[tuple[list[str], dict[str, Any]]] = []
    baseline = tmp_path / "validation" / "native-baseline.json"
    baseline.parent.mkdir()
    baseline.write_text(
        json.dumps({"schema_version": 1, "findings": [_baseline_finding("known")]}),
        encoding="utf-8",
    )

    monkeypatch.setattr(native_validation_runner, "find_kicad_cli", lambda: "kicad-cli")
    monkeypatch.setattr(
        native_validation_runner.subprocess,
        "run",
        _fake_kicad_run(commands, erc_exit=5, drc_exit=0),
    )

    result = kicad_native_validate.main(
        [
            str(tmp_path),
            "--baseline",
            str(baseline),
            "--block-new-regressions",
        ]
    )

    report_dir = tmp_path / "build" / "kicad"
    regression = json.loads((report_dir / "regression-result.json").read_text())
    summary = json.loads((report_dir / "summary.json").read_text())
    assert result == 1
    assert regression["status"] == "failed"
    assert regression["counts"]["new_regressions"] == 3
    assert regression["counts"]["resolved"] == 1
    assert summary["status"] == "regression_failed"
    assert summary["regression_gate"]["new_regressions"] == 3


def test_native_validate_allows_existing_baseline_findings(
    tmp_path: Path,
    monkeypatch,
):
    _write_project(tmp_path)
    commands: list[tuple[list[str], dict[str, Any]]] = []

    monkeypatch.setattr(native_validation_runner, "find_kicad_cli", lambda: "kicad-cli")
    monkeypatch.setattr(
        native_validation_runner.subprocess,
        "run",
        _fake_kicad_run(commands, erc_exit=5, drc_exit=5),
    )
    kicad_native_validate.main([str(tmp_path), "--report-dir", str(tmp_path / "capture")])
    capture_summary = json.loads((tmp_path / "capture" / "summary.json").read_text())
    baseline = tmp_path / "native-baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "policy": {
                    "blocks_new_findings": True,
                    "allows_existing_findings": True,
                },
                "findings": capture_summary["findings"],
            }
        ),
        encoding="utf-8",
    )

    commands.clear()
    result = kicad_native_validate.main(
        [
            str(tmp_path),
            "--baseline",
            str(baseline),
            "--block-new-regressions",
        ]
    )

    report_dir = tmp_path / "build" / "kicad"
    regression = json.loads((report_dir / "regression-result.json").read_text())
    summary = json.loads((report_dir / "summary.json").read_text())
    assert result == 0
    assert regression["status"] == "passed"
    assert regression["counts"]["new_regressions"] == 0
    assert regression["counts"]["existing"] == 3
    assert summary["status"] == "passed"


def test_native_validate_missing_baseline_fails_regression_gate(
    tmp_path: Path,
    monkeypatch,
):
    _write_project(tmp_path)
    commands: list[tuple[list[str], dict[str, Any]]] = []

    monkeypatch.setattr(native_validation_runner, "find_kicad_cli", lambda: "kicad-cli")
    monkeypatch.setattr(
        native_validation_runner.subprocess,
        "run",
        _fake_kicad_run(commands, erc_exit=0, drc_exit=0),
    )

    result = kicad_native_validate.main(
        [
            str(tmp_path),
            "--baseline",
            str(tmp_path / "missing-baseline.json"),
            "--block-new-regressions",
        ]
    )

    report_dir = tmp_path / "build" / "kicad"
    regression = json.loads((report_dir / "regression-result.json").read_text())
    assert result == 3
    assert regression["status"] == "baseline_missing"
    assert "baseline file not found" in regression["notes"][0]


def _write_project(root: Path) -> tuple[Path, Path]:
    schematic = root / "main.kicad_sch"
    pcb = root / "main.kicad_pcb"
    schematic.write_text(VALID_SCH, encoding="utf-8")
    pcb.write_text("(kicad_pcb (version 20240108) (generator test))\n", encoding="utf-8")
    return schematic, pcb


def _fake_kicad_run(
    commands: list[tuple[list[str], dict[str, Any]]],
    *,
    erc_exit: int,
    drc_exit: int,
    severity: str = "error",
):
    def fake_run(command: list[str], **kwargs: Any):
        commands.append((command, kwargs))
        if command[1:] == ["version"]:
            return subprocess.CompletedProcess(command, 0, stdout="9.0.2\n", stderr="")
        if command[1:4] == ["sch", "export", "netlist"]:
            _write_output(command, "(exported_netlist)\n")
            return subprocess.CompletedProcess(command, 0, stdout="netlist stdout\n", stderr="")
        if command[1:3] == ["sch", "erc"]:
            _write_output(
                command,
                json.dumps(
                    {
                        "violations": [
                            {
                                "severity": severity,
                                "code": "unconnected_pin",
                                "message": "Pin is not connected",
                                "item": "U1 pin 1",
                                "file": str(kwargs["cwd"] / "main.kicad_sch"),
                            }
                        ]
                    }
                ),
            )
            return subprocess.CompletedProcess(
                command,
                erc_exit,
                stdout="erc stdout\n",
                stderr="erc stderr\n",
            )
        if command[1:3] == ["pcb", "drc"]:
            _write_output(
                command,
                json.dumps(
                    {
                        "violations": [
                            {
                                "severity": severity,
                                "code": "clearance",
                                "message": "Clearance violation",
                                "item": "Net-(J1-Pad1)",
                                "file": "main.kicad_pcb",
                            },
                            {
                                "severity": severity,
                                "code": "schematic_parity_mismatch",
                                "message": "Schematic parity mismatch",
                                "item": "R1",
                                "file": "main.kicad_pcb",
                            },
                        ]
                    }
                ),
            )
            return subprocess.CompletedProcess(
                command,
                drc_exit,
                stdout="drc stdout\n",
                stderr="drc stderr\n",
            )
        raise AssertionError(f"unexpected command: {command}")

    return fake_run


def _write_output(command: list[str], text: str) -> None:
    output = Path(command[command.index("--output") + 1])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def _baseline_finding(fingerprint: str) -> dict[str, str]:
    return {
        "fingerprint": fingerprint,
        "source": "erc",
        "severity": "error",
        "type": "old",
        "message": "old finding",
        "item": "J1",
        "path": "main.kicad_sch",
    }


VALID_SCH = """\
(kicad_sch
  (version 20231120)
  (generator "ai-probe-router")
  (generator_version "1.0.0")
  (uuid 11111111-1111-4111-8111-111111111111)
  (paper "A4")
  (lib_symbols)
  (sheet_instances
    (path "/"
      (page "1")
    )
  )
)
"""
