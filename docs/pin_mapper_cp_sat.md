# CP-SAT Pin Mapper

PR3 adds an optional CP-SAT pin-mapping mode behind a feature flag. The existing greedy mapper remains the default and safe path.

## Configuration

```yaml
pin_mapper:
  mode: greedy          # greedy | cp_sat | compare
  fallback_to_greedy: true
  require_ortools: false
  selected_output: greedy

  objective_weights:
    preferred_pin: 100
    capability_match: 80
    current_margin: 30
    preserve_spare_pins: 5
    duplicate_probe_grouping: 20
    differential_pair_adjacency: 50
    route_length: 1
```

Defaults preserve existing behavior:

- `mode: greedy`
- `fallback_to_greedy: true`
- `selected_output: greedy`

## Modes

| Mode | Behavior |
|------|----------|
| `greedy` | Uses the existing deterministic greedy/backtracking mapper. |
| `cp_sat` | Uses the OR-Tools CP-SAT mapper when available. |
| `compare` | Runs greedy and CP-SAT, writes comparison reports, and uses `selected_output` for generated output. |

## Missing OR-Tools

- `greedy` does not require OR-Tools.
- `cp_sat` with fallback enabled uses greedy and reports `ORTOOLS_MISSING_FALLBACK_TO_GREEDY`.
- `cp_sat` with fallback disabled or `require_ortools: true` reports `CP_SAT_REQUIRED_BUT_ORTOOLS_MISSING`.
- `compare` writes a comparison report and keeps greedy output when CP-SAT is unavailable.

## Hard Constraints

The CP-SAT mapper starts with these hard constraints:

- Each required net maps to one physical pin.
- A physical pin cannot be reused unless represented as a separate valid duplicate assignment.
- Required capabilities must match the net role.
- Preferred pins are honored when a valid preferred candidate exists.
- Power pins must satisfy current requirements.
- Ground duplicate probe count requires enough valid ground-capable pins.
- Differential pair assignments must use adjacent pins.

## Compare Reports

Compare mode writes:

- `pin_mapper_compare_report.txt`
- `pin_mapper_compare_report.json`

The reports include selected output, assignment differences, objective scores, warnings, and solver errors.

## Readiness

Readiness treats CP-SAT and compare behavior as reviewable or blocking:

- Warning: `CP_SAT_SOLVER_USED`
- Warning: `PIN_MAPPER_COMPARE_DIFFERENCE`
- Warning: `ORTOOLS_MISSING_FALLBACK_TO_GREEDY`
- Error: `CP_SAT_REQUIRED_BUT_ORTOOLS_MISSING`
- Error: `CP_SAT_NO_FEASIBLE_MAPPING`
- Error: `PIN_MAPPING_CONSTRAINT_CONFLICT`
