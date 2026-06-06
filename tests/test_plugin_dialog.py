"""Tests for KiCad plugin dialog integration.

These tests verify the fallback path (no wxPython).  The wxPython path is
exercised manually inside KiCad.
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

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
    def __init__(self, nets: list[str]):
        self._nets = nets

    def GetNetInfo(self):
        return self

    def NetsByName(self):
        return {n: _FakeNet(n) for n in self._nets}


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
