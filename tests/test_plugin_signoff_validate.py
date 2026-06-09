"""Tests for manual plugin signoff evidence validation."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import plugin_signoff_validate


def test_plugin_signoff_validate_skips_missing_evidence(tmp_path: Path, capsys):
    result = plugin_signoff_validate.main([str(tmp_path / "missing.json")])

    assert result == 0
    assert "plugin signoff evidence not found" in capsys.readouterr().out


def test_plugin_signoff_validate_requires_missing_evidence(tmp_path: Path):
    result = plugin_signoff_validate.main([
        str(tmp_path / "missing.json"),
        "--require-signoff",
    ])

    assert result == 1


def test_plugin_signoff_validate_accepts_complete_evidence(
    tmp_path: Path,
    capsys,
):
    evidence = tmp_path / "plugin_signoff.json"
    evidence.write_text(json.dumps(_complete_evidence()), encoding="utf-8")

    result = plugin_signoff_validate.main([str(evidence), "--require-signoff"])

    assert result == 0
    assert "plugin signoff evidence accepted" in capsys.readouterr().out


def test_plugin_signoff_validate_rejects_incomplete_evidence(tmp_path: Path, capsys):
    evidence = _complete_evidence()
    evidence["action_plugin_visible"] = False
    evidence["kicad_version"] = ""
    path = tmp_path / "plugin_signoff.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")

    result = plugin_signoff_validate.main([str(path)])

    assert result == 1
    output = capsys.readouterr().out
    assert "action_plugin_visible must be true" in output
    assert "kicad_version is required" in output


def _complete_evidence() -> dict[str, object]:
    return {
        "action_plugin_generates_output": True,
        "action_plugin_visible": True,
        "error_dialog_captures_cli_failure": True,
        "evidence_link": "https://example.invalid/signoff",
        "kicad_version": "8.0.0",
        "notes": ["tested in KiCad PCB Editor"],
        "os": "Windows 11",
        "plugin_shell_no_3d_opened": True,
        "report_tabs_rendered": True,
        "temporary_config_selects_nontrivial_nets": True,
        "three_d_view_checked": True,
    }
