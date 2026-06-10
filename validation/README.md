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

The current audio baseline was captured from a successful KiCad 9 CI run and
records the known warning-level parity backlog. The generated smoke project does
not use a baseline; it remains a zero-tolerance native validation check.

To capture a fresh baseline artifact from GitHub Actions:

```bash
./scripts/capture-baseline.sh
```

Then create and review the baseline:

```bash
python scripts/kicad_native_baseline_create.py \
  --summary .artifacts/baseline-capture/native-validation-reports/audio/summary.json \
  --output examples/audio_player_project/ci/native-baseline.kicad9.json \
  --repo flash555588/ai-probe-router \
  --workflow ci.yml \
  --job native-kicad \
  --artifact native-validation-reports \
  --report-subdir validation/reports/audio \
  --commit-sha <source-commit> \
  --run-url <source-run-url> \
  --generated-at-utc <timestamp>

python scripts/kicad_native_baseline_review.py \
  --baseline examples/audio_player_project/ci/native-baseline.kicad9.json \
  --summary .artifacts/baseline-capture/native-validation-reports/audio/summary.json
```

Then compare a current run with:

```bash
python scripts/kicad_native_regression_gate.py \
  --current validation/reports/audio/summary.json \
  --baseline examples/audio_player_project/ci/native-baseline.kicad9.json \
  --output validation/reports/audio/regression-result.json
```

Baseline updates are review items. They should document why issue categories
were accepted, resolved, or changed. PRs that modify native baselines are also
checked by `.github/workflows/baseline-pr-check.yml` for metadata completeness,
ISO timestamps, commit validity, count consistency, and fingerprint freshness.
