# KiCad Plugin Shell

A PyQt6 GUI that visualizes ai-probe-router reports: footprint preview, resource allocation, route import status, and a 3D board view with STEP support.

## Installation

The plugin shell requires PyQt6 and VTK:

```bash
pip install PyQt6 vtk
# or using the project's extras:
pip install -e ".[plugin]"
```

## Usage

### CLI

```bash
# Tables only (no 3D dependencies required)
apr plugin-shell output/

# With optional STEP board model
apr plugin-shell output/ --step 3D_PCB1.step

# Disable 3D view
apr plugin-shell output/ --no-3d
```

### Standalone Python

```bash
python -m ai_probe_router.ui.plugin_shell output/
python -m ai_probe_router.ui.plugin_shell output/ 3D_PCB1.step
```

### From Python

```python
from pathlib import Path
from ai_probe_router.ui.plugin_shell import KiCadPluginShell

shell = KiCadPluginShell(Path("output"), step_path=Path("3D_PCB1.step"))
shell.load_reports()
shell.run()
```

### YAML Configuration

```yaml
plugin_shell:
  step_file: "3D_PCB1_2026-06-07.step"
  enable_3d: true
  fallback_to_2d_board: true
```

## Tabs

### Footprint Preview

Displays planned footprints from PR6 in a table:

- Reference, module, footprint name, position, side, role
- Issues list with severity icons (error/warning/info)
- Color-coded by status

### Resource Allocation

Shows PR5 allocation results:

- **Bus Assignments** — I2C/SPI/UART bus IDs, module references, I2C addresses
- **Power Domains** — voltage, budget, requested current, headroom percentage

### Route Import

Displays PR2 readiness blockers and warnings:

- Blockers (red)
- Warnings (orange)

### 3D View

VTK-based 3D visualization with three-panel layout:

| Left | Center | Right |
|------|--------|-------|
| Severity filters | VTK 3D view | Module detail panel |

**Board rendering:**
- STEP file → real 3D board (when available)
- Missing STEP → synthetic extruded board outline (fallback)
- STEP parse failure → warning banner + fallback board

**Footprint overlays:**
- Boxes at planned (x, y, z) positions
- **Color coding**:
  - LimeGreen = OK / info
  - Gold = warning
  - Tomato = error / collision
- Severity filters toggle visibility per overlay

**Click-to-inspect:**
- Left-click a footprint box → module details appear in right panel
- Details include: footprint name, resource assignments, route/import issues, readiness codes

**Mouse controls:**
- Rotate, zoom, pan (trackball camera)

## Menu

- **File → Open Output Folder** — switch to a different output directory
- **File → Refresh Reports** — reload all JSON reports
- **File → Exit**

## Report files consumed

| Report | File | Source PR |
|--------|------|-----------|
| Footprint Preview | `footprint_preview_report.json` | PR6 |
| Resource Allocation | `resource_allocation_report.json` | PR5 |
| Readiness | `readiness_report.json` | PR2 |

## Architecture

```
ai_probe_router/ui/
├── plugin_shell.py          # Main window, tabs, menu
├── report_loader.py         # JSON report parsers
├── report_model.py          # Merged per-module view model
├── coordinate_transform.py  # PCB → world coordinate mapping
├── severity_filter.py       # Error/Warning/Info visibility state
├── footprint_overlay.py     # Footprint → 3D overlay items
├── step_scene_loader.py     # STEP / fallback scene loading
└── vtk_3d_view.py           # VTK 3D scene manager + picking
```

All heavy dependencies (PyQt6, vtk) are imported **lazily** so the core library can be used without them installed.

## Safety

- Plugin shell is **standalone** — it never modifies source PCB files
- It only reads JSON report files from the output directory
- No KiCad plugin registration required for the prototype
- Fallback rendering ensures the GUI is functional even without STEP files or VTK installed
