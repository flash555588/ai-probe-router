# ai-probe-router

AI-assisted KiCad probe/test interface designer. Automatically generates testpoints, maps probe pins to development board connectors, and validates placement against electrical, mechanical, and manufacturing constraints.

## Features

- **KiCad S-expression parser** — reads `.kicad_sch` and `.kicad_pcb` files, supports `gr_rect`, `gr_line`, `gr_circle` board outlines
- **Net classifier** — rule-based classification into power, ground, debug, communication, analog, high-speed, clock, reset, GPIO
- **Constraint-aware placement** — generates candidate positions scored by routing cost, board edge clearance, component collision avoidance, and probe spacing
- **Pin mapper** — maps target nets to development board pins using capability matching, current ratings, and user preferences
- **Schematic + PCB generation** — inserts testpoint symbols/footprints and connector symbols/footprints into KiCad files
- **Verification** — constraint validation, ERC/DRC via `kicad-cli`, coverage reports

## Installation

```bash
# Clone
git clone https://github.com/flash555588/ai-probe-router.git
cd ai-probe-router

# Install (requires Python 3.12+)
uv pip install -e ".[dev]"
```

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

nets_to_expose:
  - net: SWDIO
    role: debug
    required: true
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
```

## Architecture

```
ai_probe_router/
├── ai/                  # Net classifier
├── eda_adapters/kicad/  # S-expression parser, PCB/schematic read/write
├── models/              # Board, Net, Probe, Constraints, DevBoard
├── solvers/             # Constraint checker, placement solver, pin mapper, routing cost
└── verification/        # Coverage and pin mapping reports
```

**Design principle**: AI assists with classification and suggestions; deterministic rules enforce correctness. The constraint engine validates every placement — the system never trusts AI-generated geometry without verification.

## CLI Commands

| Command | Description |
|---------|-------------|
| `apr generate <config> [-d dir]` | Full pipeline: parse, place, generate, verify |
| `apr inspect <pcb_file>` | List nets with roles and pad counts |
| `apr inspect-sch <sch_file>` | List components, labels, wires |
| `apr validate <pcb_file>` | Validate existing testpoint placement |

## Development

```bash
# Run tests
pytest

# Lint
ruff check .
```

## License

MIT
