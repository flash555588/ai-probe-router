# Library Governance

The `apr library check` command validates chip, module, and dev-board YAML libraries before they are used in designs.

## Usage

```bash
# Text report (default)
apr library check libraries/

# JSON report
apr library check libraries/ --format json

# Strict mode: warnings become errors
apr library check libraries/ --strict

# Skip experimental modules
apr library check libraries/ --no-include-experimental
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Valid |
| 2 | Valid with warnings |
| 3 | Invalid |
| 1 | Runtime/tool error |

## Validation layers

### Layer 1 — JSON schema

Checks structure:

- Required fields present
- Field types correct
- Enum values valid
- Numeric ranges valid
- Unknown fields rejected (when `additionalProperties: false`)

### Layer 2 — Semantic validation

Checks meaning:

- Chip pins reference declared voltage domains
- Chip interfaces reference existing pins
- Module components reference known chips
- I2C addresses are in valid range (`0x08`–`0x77`)
- Dev-board pins with `is_ground` have `GND` capability
- Current ratings are non-negative

### Layer 3 — Compatibility validation

Checks cross-file references:

- Module package options exist on referenced chip

## Schema files

| Schema | File |
|--------|------|
| Chip | `schemas/chip_definition.schema.json` |
| Module | `schemas/module_definition.schema.json` |
| Dev board | `schemas/dev_board.schema.json` |
| Project config | `schemas/project_config.schema.json` |

## Adding a new chip

1. Create `libraries/chips/<category>/<mpn>.yaml`
2. Run `apr library check libraries/`
3. Fix any errors or warnings
4. Commit

## Adding a new module

1. Create `libraries/modules/<category>/<name>.yaml`
2. Ensure referenced chips exist in `libraries/chips/`
3. Run `apr library check libraries/`
4. Fix any errors or warnings
5. Commit
