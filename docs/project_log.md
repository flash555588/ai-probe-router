# Project Log

## PR1 Safety Baseline

Date: 2026-06-08

### Scope

PR1 converts generation readiness into a machine-readable, CI-gateable contract while preserving the existing human reports and API behavior. The implementation keeps all generated KiCad outputs under `output/` and leaves source project files untouched.

### Changes

- Added `readiness_report.json` next to `readiness_report.txt`.
- Added `ReadinessReport.to_dict()` and `ReadinessReport.write_json(path)`.
- Added readiness exit-code semantics: `PASS=0`, `PASS_WITH_REVIEW=2`, `BLOCKED=3`, and runtime/tool failure `=1`.
- Added `apr generate --strict`, which forces `cfg.process_controls.strict_signoff = true` for the current run.
- Updated `apr generate` so it reads `output/readiness_report.json` after `engine.run()` and exits with the readiness gate code.
- Kept `engine.run()` return values unchanged.
- Added golden-output regression coverage for the minimal project:
  - `main.kicad_pcb`
  - `main.kicad_sch`
  - `testpoint_report.txt`
  - `readiness_report.json`
  - `decision_manifest.json`
- Added normalization for nondeterministic UUIDs, `APR-*` run IDs, SHA1 fields, runtime platform fields, and routing durations.
- Added dedicated documentation in `docs/design_spec.md`, `docs/roadmap.md`, and this log.

### Files And Artifacts

- Runtime code:
  - `ai_probe_router/verification/readiness_report.py`
  - `ai_probe_router/verification/__init__.py`
  - `ai_probe_router/engine.py`
  - `ai_probe_router/cli.py`
- Tests:
  - `tests/test_readiness_report.py`
  - `tests/test_cli.py`
  - `tests/test_engine.py`
  - `tests/test_golden_outputs.py`
  - `tests/golden/minimal_project/`
- Documentation:
  - `README.md`
  - `docs/project_log.md`
  - `docs/design_spec.md`
  - `docs/roadmap.md`

### Verification

Focused checks completed during implementation:

```bash
pytest tests\test_readiness_report.py tests\test_cli.py tests\test_engine.py
pytest tests\test_golden_outputs.py
```

Final verification commands for this PR:

```bash
pytest
ruff check .
```

Results:

- `pytest` - 328 passed in 75.63s.
- `ruff check .` - all checks passed.

## PR2 Route Import Safety

Date: 2026-06-08

### Scope

PR2 protects imported autorouter geometry. The importer now parses SES route data into net-aware objects, validates nets/layers/geometry before mutation, and uses a transactional file workflow for `apr route`.

### Changes

- Added SES route object parsing in `ai_probe_router/routing/ses_net_resolver.py`.
- Added structured route validation in `ai_probe_router/routing/routing_validation.py`.
- Reworked `ai_probe_router/routing/ses_import.py` so parsing and validation happen before any board mutation.
- Added transactional file import in `ai_probe_router/routing/route_import_transaction.py`.
- Updated `apr route` to write a candidate board, promote a final routed board only after validation, and write `routing_import_report.txt`.
- Updated the FreeRouting bridge so imported SES validation is attached to `RoutingResult`.
- Updated readiness and decision manifest plumbing so route-import validation issues are machine-readable.
- Added optional `autoroute.import_policy` and `autoroute.validation` config parsing with safe defaults.
- Added route-import safety documentation in `docs/route_import_safety.md`.

### Verification

Focused checks completed during implementation:

```bash
pytest tests\test_ses_net_resolver.py tests\test_ses_import.py tests\test_route_import_safety.py tests\test_cli.py::test_route tests\test_readiness_report.py tests\test_freerouting_bridge.py tests\test_models.py::test_load_schema_v2_module_graph_fields
ruff check ai_probe_router\config.py ai_probe_router\engine.py ai_probe_router\routing\ses_net_resolver.py ai_probe_router\routing\routing_validation.py ai_probe_router\routing\ses_import.py ai_probe_router\routing\route_import_transaction.py ai_probe_router\routing\freerouting_bridge.py ai_probe_router\routing\__init__.py ai_probe_router\cli.py ai_probe_router\verification\readiness_report.py ai_probe_router\verification\decision_manifest.py tests\test_ses_net_resolver.py tests\test_ses_import.py tests\test_route_import_safety.py tests\test_models.py
```

Final PR2 verification commands:

```bash
pytest
ruff check .
```

Results:

- `pytest` - 341 passed in 75.85s.
- `ruff check .` - all checks passed.

## PR3 CP-SAT Pin Mapper

Date: 2026-06-08

### Scope

PR3 adds an optional CP-SAT pin mapper behind a feature flag. The existing greedy mapper remains the default, and compare mode can run both solvers while preserving greedy output by default.

### Changes

- Added `pin_mapper` config parsing with `greedy`, `cp_sat`, and `compare` modes.
- Added `ai_probe_router/solvers/pin_mapper_cp_sat.py`.
- Added `ai_probe_router/solvers/pin_mapper_compare.py`.
- Extended `MappingResult` with solver warnings and objective score metadata.
- Updated engine phase 2 to dispatch by pin-mapper mode.
- Added compare reports: `pin_mapper_compare_report.txt` and `pin_mapper_compare_report.json`.
- Added readiness warnings/errors for CP-SAT usage, fallback, compare differences, and CP-SAT blockers.
- Added CP-SAT workflow documentation in `docs/pin_mapper_cp_sat.md`.

### Verification

Focused checks completed during implementation:

```bash
pytest tests\test_pin_mapper_cp_sat.py tests\test_pin_mapper_compare.py tests\test_pin_mapper.py tests\test_models.py tests\test_engine.py tests\test_readiness_report.py
ruff check ai_probe_router\config.py ai_probe_router\engine.py ai_probe_router\solvers\pin_mapper.py ai_probe_router\solvers\pin_mapper_cp_sat.py ai_probe_router\solvers\pin_mapper_compare.py ai_probe_router\solvers\__init__.py ai_probe_router\verification\readiness_report.py ai_probe_router\verification\pin_report.py tests\test_pin_mapper_cp_sat.py tests\test_pin_mapper_compare.py
```

Final PR3 verification commands:

```bash
pytest
ruff check .
```

Results:

- `pytest` - 354 passed in 80.67s.
- `ruff check .` - all checks passed.

## PR4 Library Schema and `apr library check`

Date: 2026-06-08

### Scope

PR4 adds JSON schema validation and a `apr library check` command to keep the growing chip/module/dev-board library valid and safe to use.

### Changes

- Added `schemas/chip_definition.schema.json`, `schemas/module_definition.schema.json`, `schemas/dev_board.schema.json`, `schemas/project_config.schema.json`.
- Added `ai_probe_router/library/schema_loader.py` to load and cache schemas.
- Added `ai_probe_router/library/checker.py` with three validation layers:
  - JSON schema layer (structure, types, enums, ranges)
  - Semantic layer (voltage domain references, I2C address range, ground capability consistency)
  - Compatibility layer (chip package options cross-referenced from modules)
- Added `ai_probe_router/library/report.py` for text and JSON reports with exit codes 0/2/3.
- Added `apr library check` CLI command with `--format`, `--strict`, and `--include-experimental` options.
- Added `docs/library_governance.md`.
- Updated README, roadmap, and project log.

### Verification

Final PR4 verification commands:

```bash
pytest
ruff check .
```

Results:

- `pytest` - TBD passed.
- `ruff check .` - all checks passed.
