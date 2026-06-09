# Native KiCad Validation

Native KiCad validation is coordinated by
`ai_probe_router.verification.native_validation_runner`. The standalone script,
CI workflow, and generated-project pipeline all use this shared runner so local
and CI checks use the same strict KiCad command shape.

Local CI-equivalent command:

```bash
python scripts/kicad_native_validate.py \
  examples/audio_player_project \
  --report-dir validation/reports/audio \
  --require-kicad \
  --strict
```

The wrapper still skips cleanly when `kicad-cli` is absent unless
`--require-kicad` is supplied.

The runner executes:

```bash
kicad-cli version
kicad-cli sch export netlist --output <reports>/netlist/main.net --format kicadsexpr main.kicad_sch
kicad-cli sch erc --output <reports>/erc/erc.json --format json --exit-code-violations main.kicad_sch
kicad-cli pcb drc --output <reports>/drc/drc.json --format json --schematic-parity --exit-code-violations main.kicad_pcb
```

Schematic parity is produced by KiCad's PCB DRC command and mirrored into
`parity/parity.json` so artifact consumers have a stable parity report slot.

Report layout:

```text
validation/reports/audio/
  summary.json
  kicad-version.txt
  version.stdout.log
  version.stderr.log
  file-list.txt
  project-file-list.txt
  artifact_manifest.json
  netlist/main.net
  netlist/stdout.log
  netlist/stderr.log
  erc/erc.json
  erc/stdout.log
  erc/stderr.log
  drc/drc.json
  drc/stdout.log
  drc/stderr.log
  parity/parity.json
  parity/stdout.log
  parity/stderr.log
  grouped-findings.json
  grouped-findings.md
```

The `native-kicad` CI job runs on pull requests, pushes to `main`, and manual
workflow dispatch. It uses the pinned KiCad 9 container
`ghcr.io/inti-cmnb/kicad9_auto:1.8.5`, writes all native evidence under
`validation/reports/`, uploads `native-validation-reports` with
`if-no-files-found: error`, and fails only after the upload step has had a
chance to run.

Regression governance is baseline-driven:

```bash
python scripts/kicad_native_regression_gate.py \
  --current validation/reports/audio/summary.json \
  --baseline examples/audio_player_project/ci/native-baseline.kicad9.json \
  --output validation/reports/audio/regression-result.json
```

The gate fails when a new issue category appears or an existing category count
increases. Existing baseline findings and resolved findings do not block. A real
baseline must be captured and reviewed in an environment with KiCad 9 installed;
do not replace that review with an empty placeholder baseline.
