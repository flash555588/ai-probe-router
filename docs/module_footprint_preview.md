# Module Footprint Preview

The footprint preview mode shows which module-related footprints would be added, where they would be placed, and what collisions/keepout risks exist — without modifying the source PCB.

## Usage

Enable in your project config:

```yaml
module_footprint_preview:
  enable: false              # default: disabled
  mode: preview              # preview | emit_candidate
  write_candidate_pcb: false # never overwrites source PCB
  block_on_collision: true
  block_on_missing_footprint: false
  block_on_keepout_violation: true
  candidate_suffix: ".module-preview"
```

## Modes

### preview (default)

Generates text and JSON reports only:

- `output/footprint_preview_report.txt`
- `output/footprint_preview_report.json`

### emit_candidate

Writes a candidate PCB with the suffix configured in `candidate_suffix`:

- `output/*.module-preview.kicad_pcb`

The source PCB is never modified.

## Checks performed

- **Missing footprints** — warns or blocks depending on `block_on_missing_footprint`
- **Collisions** — planned footprints colliding with each other or existing refs
- **Board bounds** — footprints placed outside the board outline
- **Keepout violations** — footprints inside keepout zones
- **Dense regions** — warns when many footprints are planned in a small area

## Readiness integration

Blockers:

- `FOOTPRINT_PREVIEW_MISSING_REQUIRED_FOOTPRINT`
- `FOOTPRINT_PREVIEW_COLLISION`
- `FOOTPRINT_PREVIEW_OUT_OF_BOUNDS`
- `FOOTPRINT_PREVIEW_KEEPOUT_VIOLATION`

Warnings:

- `FOOTPRINT_PREVIEW_MISSING_OPTIONAL_FOOTPRINT`
- `FOOTPRINT_PREVIEW_DENSE_REGION`
- `FOOTPRINT_PREVIEW_USED_APPROXIMATE_SIZE`
- `FOOTPRINT_PREVIEW_CANDIDATE_ONLY`

## Safety

- Disabled by default — no behavior change unless explicitly enabled
- Source PCB is never modified in any mode
- Candidate PCB output is opt-in only (`write_candidate_pcb: true`)
- All checks are deterministic and conservative
