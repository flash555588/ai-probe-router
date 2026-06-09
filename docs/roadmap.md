# ai-probe-router Roadmap

## PR1 — Core Engine
- KiCad S-expression parser (`kicad_sch`, `kicad_pcb`)
- Net classifier (power, ground, debug, communication, analog, high-speed, clock, reset, GPIO)
- Constraint-aware placement scoring
- Schematic + PCB generation (testpoints, connectors, protection circuits)

## PR2 — Verification & Readiness
- Constraint validation, ERC/DRC via `kicad-cli`
- Coverage reports, manufacturing readiness reports
- Human review gates for high-speed, clock, analog, and high-current nets
- Readiness codes enum (`ReadinessCode`)

## PR3 — CP-SAT Pin Mapper
- OR-Tools CP-SAT solver for pin-to-net assignment
- Capability matching, current ratings, user preferences

## PR4 — Library Schema Check
- Module library schema validation
- Preflight checks before instantiation

## PR5 — Resource Allocator
- Bus allocation (I2C/SPI/UART), power domain assignment, connector placement
- `resource_allocator_report.json` with `schema_version: 1`

## PR6 — Module Footprint Preview
- Planned footprint generation from module libraries
- `footprint_preview_report.json` with `schema_version: 1`
- Collision and keepout detection

## PR7 — KiCad Plugin Shell
- PyQt6 GUI with footprint, resource, and route-import tabs
- Unified reports (`UnifiedReports`, `load_all_reports()`)
- Dry-run flag (`ProjectConfig.dry_run`)
- Coordinate transform (`BoardCoordinateFrame`)

## PR7.1 — 3D Plugin Experience
- **STEP scene loader** with fallback board renderer (`step_scene_loader.py`)
- **Footprint overlay actors** mapped via coordinate transforms (`footprint_overlay.py`)
- **Severity filter UI** — Error / Warning / Info toggles (`severity_filter.py`)
- **Click-to-inspect module details** — VTK picking + merged report model (`report_model.py`)
- **CLI command** — `apr plugin-shell output/ --step 3D_PCB1.step`
- **YAML config** — `plugin_shell.step_file`, `enable_3d`, `fallback_to_2d_board`

### PR7.1 Acceptance Checklist
- [x] STEP file path can be configured.
- [x] Missing STEP file does not break the GUI.
- [x] STEP parse failure falls back to board outline view.
- [x] PR6 footprints appear as 3D overlay boxes.
- [x] Overlay severity reflects PR6/PR5/PR2 issues.
- [x] Error / Warning / Info filters work.
- [x] Clicking an overlay opens module details.
- [x] Detail panel shows footprint, resources, route-import issues, and readiness codes.
- [x] Tests cover report loading, overlay mapping, severity filters, and report model.
- [x] Real STEP loading is optional in CI.
- [x] README and docs explain workflow and CLI.
- [x] pytest passes.
- [x] ruff passes.

## Future PRs (not yet scheduled)

### PR8 — Interactive Resource Optimization
- [x] Compare bus pressure and power-domain headroom.
- [x] Write `resource_optimization_report.json`.
- [x] Surface recommendations in unified report loading and plugin shell resource tab.
- [x] No automatic schematic mutation.
- [ ] GUI-based apply flow for bus and rail reassignment.

### PR9 — Candidate PCB Visual Diff
- Load `*.module-preview.kicad_pcb`
- Show added/moved footprints and issue markers
- Compare against source board

### PR10 — KiCad IPC/API Integration
- Align with KiCad's newer IPC API (not deprecated SWIG bindings)
- Real-time board update preview
