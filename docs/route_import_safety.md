# Route Import Safety

PR2 protects the autorouter import path by separating SES parsing, validation, and PCB mutation.

## Safety Invariants

- SES files are parsed into net-aware route objects before any PCB mutation.
- Imported segments and vias must have non-empty net names.
- Imported nets must exist in the KiCad board net table.
- Imported geometry must never silently resolve to KiCad net `0`.
- Imported coordinates must be finite numbers.
- Segment width must be positive.
- SES layers must be recognized or mappable to KiCad copper layers.
- File-based route import is transactional: source boards are not modified in place.

## Import Flow

```text
input/main.kicad_pcb
  -> output/main.routed.candidate.kicad_pcb
  -> parse SES routes
  -> validate nets, layers, and geometry
  -> apply routes to candidate
  -> parse candidate as post-import check
  -> output/main.routed.kicad_pcb
```

If parsing or validation fails, the candidate file may remain for debugging, but the final routed board is not promoted.

## Blocking Issue Codes

- `SES_IMPORT_PARSE_ERROR`
- `SES_IMPORT_MISSING_NET`
- `SES_IMPORT_UNKNOWN_NET`
- `SES_IMPORT_NET_ZERO`
- `SES_IMPORT_UNMAPPED_LAYER`
- `SES_IMPORT_INVALID_GEOMETRY`
- `ROUTE_CONNECTIVITY_FAILED`

## Review Warnings

A successful route import is still treated as review-sensitive. Readiness adds a `PASS_WITH_REVIEW` warning because imported autorouter geometry must be manually reviewed before manufacturing release.

## Public Artifacts

- `*.routed.candidate.kicad_pcb` - transactional candidate board.
- `*.routed.kicad_pcb` - promoted routed board, written only after validation passes.
- `routing_import_report.txt` - route import status, paths, counts, and issues.
- `readiness_report.txt` and `readiness_report.json` - include route-import blockers or review warnings when route import validation is attached to the generation run.
