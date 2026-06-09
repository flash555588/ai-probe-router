"""Tests for optional native KiCad validation wrapper."""

from __future__ import annotations

from pathlib import Path

from scripts import kicad_native_validate


def test_native_validate_skips_when_kicad_cli_missing(monkeypatch, capsys):
    monkeypatch.setattr(kicad_native_validate.shutil, "which", lambda name: None)

    result = kicad_native_validate.main([])

    assert result == 0
    assert "kicad-cli not installed; skipping" in capsys.readouterr().out


def test_native_validate_requires_kicad_when_requested(monkeypatch):
    monkeypatch.setattr(kicad_native_validate.shutil, "which", lambda name: None)

    assert kicad_native_validate.main(["--require-kicad"]) == 1


def test_native_validate_runs_expected_kicad_commands(tmp_path: Path, monkeypatch):
    schematic = tmp_path / "main.kicad_sch"
    pcb = tmp_path / "main.kicad_pcb"
    schematic.write_text(VALID_SCH, encoding="utf-8")
    pcb.write_text("(kicad_pcb (version 20240108) (generator test))\n", encoding="utf-8")
    commands = []

    monkeypatch.setattr(kicad_native_validate.shutil, "which", lambda name: "kicad-cli")

    def fake_run(command, cwd, check):
        commands.append((command, cwd, check))

    monkeypatch.setattr(kicad_native_validate.subprocess, "run", fake_run)

    result = kicad_native_validate.main([str(tmp_path)])

    assert result == 0
    assert commands[0][0][1:] == ["version"]
    assert commands[1][0][1:4] == ["sch", "export", "netlist"]
    assert commands[2][0][1:3] == ["sch", "erc"]
    assert commands[3][0][1:3] == ["pcb", "drc"]
    assert "--exit-code-violations" in commands[2][0]
    assert "--exit-code-violations" in commands[3][0]
    assert all(cwd == tmp_path for _, cwd, _ in commands)
    assert all(check is True for _, _, check in commands)


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
