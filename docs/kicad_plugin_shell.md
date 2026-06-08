# KiCad Plugin Shell

A PyQt6 GUI that visualizes ai-probe-router reports: footprint preview, resource allocation, route import status, and a 3D board view.

## Installation

The plugin shell requires PyQt6 and VTK:

```bash
pip install PyQt6 vtk
# or using the project's extras:
pip install -e ".[plugin]"
```

## Usage

Run standalone after generating reports:

```bash
python -m ai_probe_router.ui.plugin_shell output/
```

Or from Python:

```python
from pathlib import Path
from ai_probe_router.ui.plugin_shell import KiCadPluginShell

shell = KiCadPluginShell(Path("output"))
shell.load_reports()
shell.run()
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

VTK-based 3D visualization:

- Green semi-transparent board plane
- Footprint bounding boxes at planned (x, y) positions
- **Color coding**:
  - LimeGreen = OK
  - Gold = warning
  - Tomato = error/collision
- Mouse controls: rotate, zoom, pan (trackball camera)

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
├── plugin_shell.py      # Main window, tabs, menu
├── report_loader.py     # JSON report parsers
└── vtk_3d_view.py       # VTK 3D scene builder
```

All heavy dependencies (PyQt6, vtk) are imported **lazily** so the core library can be used without them installed.

## Safety

- Plugin shell is **standalone** — it never modifies source PCB files
- It only reads JSON report files from the output directory
- No KiCad plugin registration required for the prototype
