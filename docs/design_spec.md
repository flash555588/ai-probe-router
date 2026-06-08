# Design Specification

## Safety Baseline

The generator must produce reviewable artifacts without modifying the source KiCad project in place. Source schematic and PCB files are read from the project directory, while generated outputs are written under `output/`.

AI-assisted behavior is advisory. Deterministic checks remain responsible for readiness verdicts, process controls, constraints, placement, generated geometry, and reports.

## Public Outputs

Every successful `engine.run()` path writes the existing human report:

- `output/readiness_report.txt`

PR1 adds the CI-oriented JSON companion:

- `output/readiness_report.json`

The JSON shape is stable:

```json
{
  "run_id": "APR-...",
  "verdict": "PASS",
  "counts": {
    "blockers": 0,
    "warnings": 0,
    "infos": 0,
    "issues": 0
  },
  "issues": [],
  "exit_code": 0
}
```

The text report remains the human-facing summary. The JSON report is the contract for automation, CI, and release gates.

## Readiness Semantics

Readiness verdicts are ordered by severity:

| Verdict | Meaning | CLI exit code |
|---------|---------|---------------|
| `PASS` | No blocking issues and no review warnings | `0` |
| `PASS_WITH_REVIEW` | Generated output exists, but human review or process follow-up is required | `2` |
| `BLOCKED` | Required safety, graph, process, or generation checks failed | `3` |
| Tool/runtime failure | The CLI could not run or could not read valid readiness JSON | `1` |

The CLI does not infer the verdict from console text. `apr generate` reads `output/readiness_report.json` after `engine.run()` and exits with the report's `exit_code`.

## Process Controls

`apr generate --strict` forces `cfg.process_controls.strict_signoff = true` for that run only. In strict mode, process warnings that would normally produce `PASS_WITH_REVIEW` can become blocking readiness behavior.

Strict mode is intended for CI or release gates where review-only warnings should stop artifact promotion. Non-strict mode remains useful for iterative layout work because it still emits artifacts while making review requirements visible.

## Safe-Output Policy

- Generated KiCad files are written only under `output/`.
- Existing source `.kicad_pcb` and `.kicad_sch` files are never modified in place by `engine.run()`.
- Human reports and machine-readable reports share the same run ID.
- `decision_manifest.json` includes `readiness_report.json` in planned artifacts so machine gates are traceable with the generated design files.
- Golden-output tests normalize nondeterministic IDs and environment fields before comparison.

## Golden Regression Policy

The minimal-project golden test protects the shape of generated safety outputs and core KiCad edits. It compares normalized snapshots for:

- Generated PCB
- Generated schematic
- Testpoint report
- Readiness JSON
- Decision manifest

When generated output intentionally changes, update the golden snapshots in the same PR and describe the reason in `docs/project_log.md`.
