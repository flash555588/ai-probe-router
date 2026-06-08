# Roadmap

## PR2 Route-Import Safety

Add a safe route-import workflow before any richer routing automation:

- Parse FreeRouting/Specctra SES output into a reviewed intermediate model.
- Validate imported tracks and vias against board bounds, keepouts, clearances, protected nets, and expected net membership.
- Write imported routes only to generated output files.
- Add a route-import report with accepted routes, rejected routes, warnings, and rollback notes.
- Add tests for malformed SES files, wrong-net tracks, keepout violations, layer mismatches, and safe no-op behavior.

## PR3 Deterministic Resource Allocation

Strengthen deterministic planning before adding heavier optimization:

- Add resource reservation for pins, probe pads, connector pins, buses, voltage rails, area budgets, and reserved target nets.
- Make conflicts machine-readable in reports.
- Keep the existing pin mapper in place until reservation reports prove stable.
- Add fixtures that exercise duplicate resource claims and capacity limits.

## PR4 CP-SAT-Compatible Solver Interface

Prepare for optional CP-SAT without making it mandatory:

- Define solver inputs and outputs for module placement, pin assignment, and resource constraints.
- Keep deterministic fallback behavior available when OR-Tools is not installed.
- Add tests that compare deterministic fallback behavior against simple solver cases.

## PR5 Real Footprint And Library Safety

Move from scaffolded module output toward stronger KiCad library integration:

- Validate footprint availability and package compatibility before generation.
- Emit stronger component metadata for BOM, alternates, and footprint versions.
- Add library governance checks for missing footprints, mismatched package options, and unapproved substitutions.

## PR6 Broader Module Catalog

Expand functional coverage after graph, reports, and safety gates are stable:

- Add selected MCU, communication, sensor, mixed-signal, and protection modules.
- Keep module additions fixture-driven and versioned.
- Require bus, power, BOM, and routing-feasibility report coverage for every new module family.

## PR7 Hierarchical Schematics And Large-Board Planning

Add richer hierarchical output and planning once safety foundations are reliable:

- Generate reviewable hierarchical schematic sheets.
- Preserve hand-edited schematic content.
- Add large-board module placement workflows.
- Add optional AI hint ingestion only as typed, validated input to deterministic solvers.
