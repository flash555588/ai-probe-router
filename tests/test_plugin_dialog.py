"""Tests for KiCad plugin dialog integration.

These tests verify the fallback path (no wxPython).  The wxPython path is
exercised manually inside KiCad.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import yaml

# Mock pcbnew before importing the plugin (not available outside KiCad)
pcbnew_mock = ModuleType("pcbnew")
pcbnew_mock.ActionPlugin = type("ActionPlugin", (), {
    "__init__": lambda s: None,
    "defaults": lambda s: None,
    "register": lambda s: None,
})
pcbnew_mock.GetBoard = MagicMock(return_value=None)
pcbnew_mock.DisplayErrorMessage = MagicMock()
pcbnew_mock.DisplayInfoMessage = MagicMock()
pcbnew_mock.Refresh = MagicMock()
sys.modules["pcbnew"] = pcbnew_mock

from ai_probe_router.eda_adapters.kicad.plugin.action_plugin import (  # noqa: E402
    AiProbeRouterActionPlugin,
)


class FakeBoard:
    def __init__(self, nets: list[str], filename: str = ""):
        self._nets = nets
        self._filename = filename

    def GetNetInfo(self):
        return self

    def NetsByName(self):
        return {n: _FakeNet(n) for n in self._nets}

    def GetFileName(self):
        return self._filename


class _FakeNet:
    def __init__(self, name: str):
        self._name = name

    def GetNetname(self):
        return self._name


def test_select_nets_fallback_without_wx():
    """Without wxPython the plugin should select all non-trivial nets."""
    plugin = AiProbeRouterActionPlugin()
    nets = ["GND", "3V3", "SWDIO", "Net-(U1-Pad1)"]
    result = plugin._select_nets_dialog(nets)
    assert "GND" in result
    assert "SWDIO" in result
    assert "Net-(U1-Pad1)" not in result


def test_select_nets_empty_input():
    plugin = AiProbeRouterActionPlugin()
    assert plugin._select_nets_dialog([]) == []


def test_select_nets_skips_blank():
    plugin = AiProbeRouterActionPlugin()
    assert plugin._select_nets_dialog(["", "GND", ""]) == ["GND"]


def test_plugin_defaults():
    plugin = AiProbeRouterActionPlugin()
    plugin.defaults()
    assert plugin.name == "AI Probe Router"
    assert plugin.show_toolbar_button is True


def test_plugin_run_builds_temp_config_and_invokes_cli(tmp_path, monkeypatch):
    pcb_path = tmp_path / "main.kicad_pcb"
    sch_path = tmp_path / "main.kicad_sch"
    pcb_path.write_text("(kicad_pcb)", encoding="utf-8")
    sch_path.write_text("(kicad_sch)", encoding="utf-8")
    pcbnew_mock.GetBoard.return_value = FakeBoard(
        ["GND", "3V3", "SWDIO", "Net-(U1-Pad1)"],
        filename=str(pcb_path),
    )

    captured: dict[str, object] = {}

    def fake_run_cli(self, config_path, project_dir):
        config_file = Path(config_path)
        captured["project_dir"] = Path(project_dir)
        captured["config"] = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        captured["config_exists_during_run"] = config_file.exists()

    monkeypatch.setattr(AiProbeRouterActionPlugin, "_run_cli", fake_run_cli)

    plugin = AiProbeRouterActionPlugin()
    plugin.run()

    assert captured["project_dir"] == tmp_path
    assert captured["config_exists_during_run"] is True
    config = captured["config"]
    assert config["project"] == {
        "eda_tool": "kicad",
        "board_file": "main.kicad_pcb",
        "schematic_file": "main.kicad_sch",
    }
    assert [row["net"] for row in config["nets_to_expose"]] == ["GND", "3V3", "SWDIO"]
    assert not list(tmp_path.glob("*.yaml"))
