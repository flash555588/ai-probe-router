# ai-probe-router

AI-assisted KiCad probe/test interface designer. Automatically generates testpoints, maps probe pins to development board connectors, and validates placement against electrical, mechanical, and manufacturing constraints.

## Features

- **KiCad S-expression parser** — reads `.kicad_sch` and `.kicad_pcb` files, supports `gr_rect`, `gr_line`, `gr_circle` board outlines
- **Net classifier** — rule-based classification into power, ground, debug, communication, analog, high-speed, clock, reset, GPIO
- **Constraint-aware placement** — generates candidate positions scored by routing cost, board edge clearance, component collision avoidance, and probe spacing
- **Pin mapper** — maps target nets to development board pins using capability matching, current ratings, and user preferences
- **Schematic + PCB generation** — inserts testpoint symbols/footprints, connector symbols/footprints, protection circuits, fiducials, tooling holes, and keepout zones into KiCad files
- **Protection circuit generation** — series resistors for debug/reset signals (33/100 ohm), ferrite beads for power lines
- **Three probe layout modes** — distributed test pads, centralized pogo pad array, connector-based interface
- **Verification** — constraint validation, ERC/DRC via `kicad-cli`, coverage reports, manufacturing readiness reports
- **Human review gates** — flags high-speed, clock, analog, and high-current nets for mandatory review
- **Net class recommendations** — suggests trace width and clearance per net role
- **DSN export** — exports Specctra/Electra DSN for FreeRouting autorouter
- **Schema v2 module planning** - describes higher-level hardware modules such as SWD debug, GPIO expansion, and power monitoring, then selects a valid implementation from module libraries

## Installation

```bash
# Clone
git clone https://github.com/flash555588/ai-probe-router.git
cd ai-probe-router

# Core CLI + development checks (requires Python 3.12+)
uv pip install -e ".[dev]"

# Plugin shell GUI
uv pip install -e ".[plugin]"

# Optional CP-SAT solver support
uv pip install -e ".[solver]"

# Everything Python-side
uv pip install -e ".[all]"
```

### Capability Matrix

| Capability | Python extra | System dependency |
|------------|--------------|-------------------|
| Core CLI, reports, tests | `.[dev]` | none |
| Plugin shell GUI | `.[plugin]` | desktop display environment |
| 3D plugin preview | `.[plugin]` | `vtk` from the plugin extra |
| CP-SAT pin mapping | `.[solver]` | none |
| Native KiCad ERC/DRC/export | any | `kicad-cli` |
| FreeRouting bridge | any | Java + FreeRouting |

## Quick Start

### Inspect a PCB

```bash
apr inspect examples/minimal_project/main.kicad_pcb
```

### Generate testpoints

```bash
apr generate examples/sample_config.yaml -d examples/minimal_project
```

### Generate with dev board pin mapping

```bash
apr generate examples/full_config.yaml -d examples/minimal_project
```

### Validate existing testpoints

```bash
apr validate path/to/board.kicad_pcb
```

### Launch plugin shell (3D preview)

Requires `uv pip install -e ".[plugin]"`.

```bash
apr plugin-shell output/
apr plugin-shell output/ --step 3D_PCB1.step
```

## Configuration
Define your probe requirements in a YAML file:

```yaml
project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

probe_interface:
  type: test_pad          # test_pad | pogo_pad_array | connector
  side: top
  pad_diameter_mm: 1.5
  min_probe_spacing_mm: 2.54
  preferred_grid_mm: 2.54
  require_silkscreen_labels: true
  require_fiducials: true
  require_tooling_holes: true

nets_to_expose:
  - net: SWDIO
    role: debug
    required: true
    preferred_devboard_pins: [PA13]
  - net: GND
    role: ground
    required: true
    duplicate_probe_count: 4
  - net: 3V3
    role: power
    required: true
    current_ma: 300

routing_rules:
  default_trace_width_mm: 0.15
  power_trace_width_mm: 0.5

placement_rules:
  min_distance_from_board_edge_mm: 2.0

development_board:
  pin_database: path/to/dev_board_pins.yaml

protection:
  enabled: true
  debug:
    type: series_resistor
    value: "33"
    package: "0402"
  reset:
    type: series_resistor
    value: "100"
    package: "0402"
  power:
    type: ferrite_bead
    value: "600R@100MHz"
    package: "0603"
    ref_prefix: FB
```

### Schema v2 Functional Modules

Schema v2 keeps the old `nets_to_expose` format compatible, and also adds
module-level design intent:

```yaml
schema_version: 2

project:
  eda_tool: kicad
  board_file: main.kicad_pcb
  schematic_file: main.kicad_sch

hardware_platform:
  target_voltage_domains:
    - name: VDD_3V3
      voltage: 3.3
      max_current_ma: 800

functional_modules:
  - name: scalable_gpio
    type: gpio_expansion
    channels: 16
    depends_on: [debug_access]
    budget_area_mm2: 250
    preferred_region: top
    ai_hints:
      - type: sensitive_route
    allowed_interfaces: [i2c, spi]
    require_level_shift: true
    require_esd: true

routing_strategy:
  coarse_grid_mm: 5
  congestion_weight: 10
  sensitive_net_spacing_mm: 5

process_controls:
  strict_signoff: false
  require_autorouter_feedback: false
  scalability_module_warning_threshold: 20
  scalability_net_warning_threshold: 200
  waivers:
    - id: WV-1
      source: electrical_signoff
      issue_id: electrical_review_required
      owner: layout-review
      reason: external checklist completed
```

The module-planning pass is rule based. It writes selected implementations,
module library preflight diagnostics, module graph diagnostics, bus/power
reports, a per-module BOM, and routing feasibility corridors. It also reports
module, implementation, chip, and footprint version metadata for compatibility
and substitution review. Generated hierarchical sheet stubs are written under
`output/generated_modules/` when a schematic is available. AI hints are advisory
only and are reported when ignored. The process-control pass covers electrical
signoff gaps, power-integrity assumptions, DFM, fixture realism, library
governance, waivers, incremental diffs, scalability thresholds, autorouter
feedback, and reproducibility manifests.

## Architecture

```
ai_probe_router/
├── ai/                  # Net classifier
├── eda_adapters/kicad/  # S-expression parser, PCB/schematic read/write
├── models/              # Board, Net, Probe, Constraints, DevBoard, Protection
├── solvers/             # Constraint checker, placement solver, pin mapper, routing cost
├── routing/             # DSN export for autorouter
└── verification/        # Coverage, pin mapping, manufacturing readiness reports
```

**Design principle**: AI assists with classification and suggestions; deterministic rules enforce correctness. The constraint engine validates every placement — the system never trusts AI-generated geometry without verification.

## CLI Commands

| Command | Description |
|---------|-------------|
| `apr generate <config> [-d dir]` | Full pipeline: parse, place, generate, verify |
| `apr inspect <pcb_file>` | List nets with roles and pad counts |
| `apr inspect-sch <sch_file>` | List components, labels, wires |
| `apr validate <pcb_file>` | Validate existing testpoint placement |

## Output Files

After running `apr generate`, the `output/` directory contains:

Text reports, `bom_report.csv`, and generated module sheets include a deterministic
`APR-*` run ID so outputs from the same planning run can be traced together.

| File | Description |
|------|-------------|
| `*.kicad_pcb` | Updated PCB with testpoints, connector, fiducials, tooling holes, keepouts |
| `*.kicad_sch` | Updated schematic with testpoint symbols, connector, protection circuits |
| `*.kicad_pro` | KiCad project file carrying the configured design rules so native DRC validates against them |
| `testpoint_report.txt` | Coverage report with net class recommendations and review gates |
| `pin_mapping_report.txt` | Development board pin assignment table |
| `module_report.txt` | Schema v2 module selections, rejected alternatives, and review gates |
| `module_library_preflight_report.txt` | Module library YAML structure, metadata, duplicate, and request coverage checks |
| `module_graph_report.txt` | Module instances, dependencies, generated resources, graph diagnostics |
| `module_compatibility_report.txt` | Module, implementation, chip, footprint, and alternate compatibility matrix |
| `resource_allocation_report.json` | Deterministic bus and power allocation data for schema-v2 modules |
| `resource_optimization_report.json` | Advisory bus/rail optimization recommendations with no automatic mutation |
| `bus_report.txt` | Module bus grouping, I2C address conflicts, pull-up coverage |
| `power_report.txt` | Module voltage-domain and rail usage |
| `routing_feasibility_report.txt` | Coarse module corridor, congestion, and sensitivity analysis |
| `module_placement_report.txt` | Module regions, component placement scaffolds, probe/connector zones |
| `module_instantiation_report.txt` | Generated module sheet stubs and child schematic files |
| `generated_modules/*.kicad_sch` | Generated hierarchical module child sheets |
| `bom_report.csv` | Per-module generated component rows |
| `manufacturing_report.txt` | Manufacturing readiness summary |
| `design_process_report.txt` | Process gaps, waivers, signoff coverage, and next actions |
| `readiness_report.txt` | Top-level PASS, PASS_WITH_REVIEW, or BLOCKED verdict |
| `decision_manifest.json` | Run ID, tool versions, decisions, waivers, artifact hashes, and diff summary |
| `routing.dsn` | Specctra DSN for FreeRouting autorouter |

## Development

```bash
# Run tests
pytest --tb=short -ra -q

# Lint
ruff check .

# Audit Python dependencies
pip-audit --progress-spinner off
```

## License

MIT
