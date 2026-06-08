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
