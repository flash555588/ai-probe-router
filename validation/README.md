# Native Validation Governance

Native KiCad validation writes machine-readable evidence under
`validation/reports/` in CI. Local runs can use the same layout:

```bash
python scripts/kicad_native_validate.py \
  examples/audio_player_project \
  --report-dir validation/reports/audio \
  --require-kicad \
  --strict
```

Regression gating is intentionally baseline-driven. A reviewed KiCad 9 baseline
should be captured from a native environment and committed as a project-specific
file, for example:

```text
examples/audio_player_project/ci/native-baseline.kicad9.json
```

Then compare a current run with:

```bash
python scripts/kicad_native_regression_gate.py \
  --current validation/reports/audio/summary.json \
  --baseline examples/audio_player_project/ci/native-baseline.kicad9.json \
  --output validation/reports/audio/regression-result.json
```

Baseline updates are review items. They should document why issue categories
were accepted, resolved, or changed.
