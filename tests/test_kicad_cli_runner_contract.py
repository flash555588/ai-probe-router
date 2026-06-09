"""Tests for low-level KiCad CLI command contract."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from ai_probe_router.eda_adapters.kicad import cli_runner


def test_run_erc_uses_exit_code_violations(tmp_path: Path, monkeypatch):
    schematic = tmp_path / "main.kicad_sch"
    schematic.write_text("(kicad_sch)", encoding="utf-8")
    commands: list[list[str]] = []

    monkeypatch.setattr(cli_runner, "find_kicad_cli", lambda: "kicad-cli")
    monkeypatch.setattr(
        cli_runner.subprocess,
        "run",
        _fake_run(commands, {"violations": []}),
    )

    result = cli_runner.run_erc(schematic, tmp_path)

    assert result.ok is True
    assert commands[0][1:3] == ["sch", "erc"]
    assert "--exit-code-violations" in commands[0]


def test_run_drc_uses_schematic_parity_and_exit_code_violations(
    tmp_path: Path,
    monkeypatch,
):
    pcb = tmp_path / "main.kicad_pcb"
    pcb.write_text("(kicad_pcb)", encoding="utf-8")
    commands: list[list[str]] = []

    monkeypatch.setattr(cli_runner, "find_kicad_cli", lambda: "kicad-cli")
    monkeypatch.setattr(
        cli_runner.subprocess,
        "run",
        _fake_run(commands, {"violations": []}),
    )

    result = cli_runner.run_drc(pcb, tmp_path)

    assert result.ok is True
    assert commands[0][1:3] == ["pcb", "drc"]
    assert "--schematic-parity" in commands[0]
    assert "--exit-code-violations" in commands[0]


def test_cli_runner_does_not_silently_ignore_footprint_mismatch(
    tmp_path: Path,
    monkeypatch,
):
    pcb = tmp_path / "main.kicad_pcb"
    pcb.write_text("(kicad_pcb)", encoding="utf-8")
    commands: list[list[str]] = []

    monkeypatch.setattr(cli_runner, "find_kicad_cli", lambda: "kicad-cli")
    monkeypatch.setattr(
        cli_runner.subprocess,
        "run",
        _fake_run(
            commands,
            {
                "violations": [
                    {
                        "severity": "error",
                        "type": "lib_footprint_mismatch",
                        "message": "Footprint does not match library copy",
                    }
                ]
            },
        ),
    )

    result = cli_runner.run_drc(pcb, tmp_path)

    assert result.ok is False
    assert result.violations[0]["type"] == "lib_footprint_mismatch"


def _fake_run(commands: list[list[str]], payload: dict[str, Any]):
    def fake_run(command: list[str], **kwargs: Any):
        commands.append(command)
        output = Path(command[command.index("--output") + 1])
        output.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    return fake_run
