"""KiCad PCB Editor action plugin for ai-probe-router.

Place this package in KiCad's plugin search path, e.g.:

  Windows: %APPDATA%/kicad/9.0/scripting/plugins/ai_probe_router
  Linux:   ~/.local/share/kicad/9.0/scripting/plugins/ai_probe_router
  macOS:   ~/Documents/KiCad/9.0/scripting/plugins/ai_probe_router

On KiCad startup the plugin registers a new tool in the PCB Editor toolbar.
"""

from __future__ import annotations

from .action_plugin import AiProbeRouterActionPlugin


def register_plugin():
    """Register the plugin with pcbnew."""
    plugin = AiProbeRouterActionPlugin()
    plugin.register()


# KiCad discovers plugins by looking for pcbnew.ActionPlugin subclasses
# or by calling register() on an instance.  We expose the class so that
# manual installs can also do::
#
#   from ai_probe_router.eda_adapters.kicad.plugin import AiProbeRouterActionPlugin
#   AiProbeRouterActionPlugin().register()
__all__ = ["AiProbeRouterActionPlugin", "register_plugin"]
