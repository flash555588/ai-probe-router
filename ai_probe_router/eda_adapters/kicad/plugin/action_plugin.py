"""KiCad action plugin entry point.

Implements pcbnew.ActionPlugin to add a toolbar button that launches
ai-probe-router's generate pipeline against the currently open board.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pcbnew

# wxPython is bundled with KiCad; gracefully degrade if absent (tests/CI)
try:
    from .dialog import NetSelectorDialog
except Exception:  # noqa: BLE001
    NetSelectorDialog = None  # type: ignore[misc,assignment]


class AiProbeRouterActionPlugin(pcbnew.ActionPlugin):
    """KiCad PCB Editor plugin for AI-assisted probe interface design."""

    def defaults(self) -> None:
        self.name = "AI Probe Router"
        self.category = "Probe / Test Interface"
        self.description = (
            "Automatically generate testpoints, connectors, and protection "
            "circuits for the current PCB."
        )
        self.show_toolbar_button = True
        self.icon_file_name = str(Path(__file__).with_suffix(".png"))
        # Fallback if icon is missing — KiCad will show a generic icon
        if not Path(self.icon_file_name).exists():
            self.icon_file_name = ""

    def run(self) -> None:
        board = pcbnew.GetBoard()
        if board is None:
            pcbnew.DisplayErrorMessage(
                self.parent, "No board is currently open."
            )
            return

        pcb_path = Path(board.GetFileName())
        if not pcb_path.exists():
            pcbnew.DisplayErrorMessage(
                self.parent,
                "Save the board before running AI Probe Router.",
            )
            return

        # Derive project directory and schematic path from PCB path
        project_dir = pcb_path.parent
        sch_path = project_dir / (pcb_path.stem + ".kicad_sch")

        # Build a minimal on-the-fly config from the open board nets
        nets = [
            n.GetNetname()
            for n in board.GetNetInfo().NetsByName().values()
        ]
        nets_to_expose = self._select_nets_dialog(nets)
        if not nets_to_expose:
            return

        config = {
            "project": {
                "eda_tool": "kicad",
                "board_file": pcb_path.name,
                "schematic_file": sch_path.name if sch_path.exists() else "",
            },
            "probe_interface": {
                "type": "test_pad",
                "side": "top",
                "pad_diameter_mm": 1.5,
                "min_probe_spacing_mm": 2.54,
                "preferred_grid_mm": 2.54,
                "require_silkscreen_labels": True,
                "require_fiducials": True,
                "require_tooling_holes": True,
            },
            "nets_to_expose": [
                {"net": n, "role": "digital", "required": True}
                for n in nets_to_expose
            ],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, dir=project_dir,
        ) as tmp:
            import yaml
            yaml.dump(config, tmp)
            config_path = tmp.name

        try:
            self._run_cli(config_path, project_dir)
        finally:
            os.unlink(config_path)

    def _select_nets_dialog(self, nets: list[str]) -> list[str]:
        """Return nets selected by the user.

        Uses wxPython when running inside KiCad; falls back to selecting
        all non-trivial nets in headless environments (tests/CI).
        """
        if NetSelectorDialog is not None:
            try:
                import wx
                dlg = NetSelectorDialog(self.parent, nets)
                if dlg.ShowModal() == wx.ID_OK:
                    return dlg.selected
                return []
            except Exception:  # noqa: BLE001
                pass  # fall through to default behaviour

        # Fallback: expose all non-trivial nets automatically
        selected = [n for n in nets if n and not n.startswith("Net-(")]
        return selected

    def _run_cli(self, config_path: str | Path, project_dir: str | Path) -> None:
        """Invoke the ai-probe-router CLI in a subprocess."""
        cmd = [
            "apr", "generate", str(config_path),
            "-d", str(project_dir),
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(project_dir),
            )
        except FileNotFoundError:
            pcbnew.DisplayErrorMessage(
                self.parent,
                "'apr' command not found. Is ai-probe-router installed and on PATH?",
            )
            return
        except subprocess.TimeoutExpired:
            pcbnew.DisplayErrorMessage(
                self.parent,
                "AI Probe Router timed out after 5 minutes.",
            )
            return

        if proc.returncode == 0:
            pcbnew.DisplayInfoMessage(
                self.parent,
                "AI Probe Router finished successfully.\n"
                f"Output written to {Path(project_dir) / 'output'}",
            )
            # Refresh board view so new footprints appear
            pcbnew.Refresh()
        else:
            pcbnew.DisplayErrorMessage(
                self.parent,
                f"AI Probe Router failed:\n{proc.stderr or proc.stdout}",
            )
