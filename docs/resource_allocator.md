# Resource Allocator

The resource allocator adds deterministic multi-module planning for buses, power domains, and connector pins.

## Usage

Enable in your project config:

```yaml
resource_allocator:
  enable: true
  bus_allocation_strategy: first_fit    # first_fit | best_fit
  power_allocation_strategy: max_headroom
  connector_allocation_strategy: minimize_spread
allow_partial_allocation: false
```

When enabled, generation writes two JSON artifacts:

- `resource_allocation_report.json` records the deterministic bus and rail allocation.
- `resource_optimization_report.json` records read-only recommendations for overloaded
  rails, near-limit rails, crowded buses, and unresolved bus/address conflicts.

Optimization recommendations are advisory only. They are designed for an interactive UI
or human review flow and do not mutate KiCad files or project YAML.

## Allocation layers

### Bus allocation

Assigns modules to shared I2C/SPI/UART buses:

- Checks for I2C address conflicts
- Creates new buses when conflicts cannot be resolved on existing buses
- Flags near-limit conditions when buses have many devices

### Power domain allocation

Sums module currents per voltage domain:

- Compares total draw against platform domain budgets
- Reports overloads as errors
- Reports headroom below 20% as warnings

### Connector allocation (placeholder)

Reserved for PR6. Will track pin usage for probes, signals, and reserved pins.

## Readiness integration

When enabled, the resource allocator feeds into the readiness report:

- `BUS_ALLOCATION_NEAR_LIMIT` → warning
- `BUS_ADDRESS_CONFLICT_UNRESOLVED` → error
- `POWER_DOMAIN_OVERLOAD` → error
- `POWER_DOMAIN_NEAR_LIMIT` → warning
- `RESOURCE_ALLOCATOR_DISABLED` → info (when disabled)

## Safety

- If `allow_partial_allocation: false`, any error blocks the module plan.
- If `allow_partial_allocation: true`, errors are reported but planning continues if any buses are assigned.
- The existing greedy module selector remains the default entry point.
- Optimization recommendations always set `safe_to_apply_automatically: false`
  until an explicit edit/apply workflow exists.
