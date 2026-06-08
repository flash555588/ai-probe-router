# Roadmap

## PR2 Route-Import Safety

Add a safe route-import workflow before any richer routing automation:

- Parse FreeRouting/Specctra SES output into a reviewed intermediate model.
- Validate imported tracks and vias against board bounds, keepouts, clearances, protected nets, and expected net membership.
- Write imported routes only to generated output files.
- Add a route-import report with accepted routes, rejected routes, warnings, and rollback notes.
- Add tests for malformed SES files, wrong-net tracks, keepout violations, layer mismatches, and safe no-op behavior.

Status: started in `pr2-route-import-safety`. Core net-aware SES parsing, validation, transactional import, readiness integration, and focused tests are implemented.

## PR3 CP-SAT Pin Mapper Behind Feature Flag

Add optional global pin mapping while preserving the existing greedy mapper as the default:

- Parse `pin_mapper.mode` as `greedy`, `cp_sat`, or `compare`.
- Use OR-Tools CP-SAT only when explicitly selected.
- Fall back to greedy when allowed and report warnings.
- Write compare reports without changing generated output by default.
- Surface CP-SAT warnings and blockers in readiness.

Status: started in `pr3-cpsat-pin-mapper`. Config parsing, CP-SAT wrapper, compare reports, engine dispatch, readiness warnings, and focused tests are implemented.

## PR4 Library Schema And `apr library check`

Add schema validation and a library-check command so chip/module/dev-board libraries can grow safely without breaking normal generation:

- JSON schemas for chip, module, dev-board, and project config.
- Three validation layers: JSON schema, semantic, compatibility.
- `apr library check` with text/JSON output, strict mode, and CI-friendly exit codes.
- Library governance documentation.

Status: started in `pr4-library-schema-check`. Schemas, checker, report, CLI integration, tests, and docs are implemented.

## PR5 Resource Allocator

Strengthen deterministic planning before adding heavier optimization:

- Add resource reservation for pins, probe pads, connector pins, buses, voltage rails, area budgets, and reserved target nets.
- Make conflicts machine-readable in reports.
- Keep the existing pin mapper in place until reservation reports prove stable.
- Add fixtures that exercise duplicate resource claims and capacity limits.

## PR6 Real Module Footprint Preview

Move from scaffolded module output toward stronger KiCad library integration:

- Validate footprint availability and package compatibility before generation.
- Emit stronger component metadata for BOM, alternates, and footprint versions.
- Add library governance checks for missing footprints, mismatched package options, and unapproved substitutions.

## PR7 KiCad Plugin Shell

Add a thin KiCad-facing workflow after CLI safety surfaces are stable:

- Provide a shell plugin that launches existing validation/generation commands.
- Keep CLI behavior authoritative.
- Avoid adding new solver or module-library behavior inside the GUI shell.

## Later: Broader Module Catalog

Expand functional coverage after graph, reports, and safety gates are stable:

- Add selected MCU, communication, sensor, mixed-signal, and protection modules.
- Keep module additions fixture-driven and versioned.
- Require bus, power, BOM, and routing-feasibility report coverage for every new module family.
