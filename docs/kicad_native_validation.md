# Native KiCad Validation

PR6 adds a project-level schematic healthcheck that validates generated KiCad
schematic structure without requiring KiCad to be installed. Native KiCad
validation is still the final production gate when `kicad-cli` is available.

Run the optional wrapper from the repository root:

```bash
python scripts/kicad_native_validate.py examples/audio_player_project
```

By default, the wrapper skips gracefully when `kicad-cli` is missing. For
PR/release CI where KiCad is installed and required:

```bash
python scripts/kicad_native_validate.py examples/audio_player_project --require-kicad
```

The wrapper runs:

```bash
kicad-cli version
kicad-cli sch export netlist --output build/kicad/main.net --format kicadsexpr main.kicad_sch
kicad-cli sch erc --output build/kicad/erc.json --format json main.kicad_sch
kicad-cli pcb drc --output build/kicad/drc.json --format json --schematic-parity main.kicad_pcb
```

The `native-kicad` CI job runs on pull requests, pushes to `main`, and manual
workflow dispatch. It uses the pinned KiCad 9 container
`ghcr.io/inti-cmnb/kicad9_auto:1.8.5` so PR review and main-branch validation
share one native-tool baseline. Local verification has also been run against
KiCad CLI 9.0.2 from the official macOS bundle.

CI uploads `examples/audio_player_project/build/kicad/` as the
`native-kicad-reports` artifact even when the native job fails. That artifact
should contain the generated netlist plus ERC/DRC JSON reports when KiCad
reaches those stages.

Interpretation:

- Hard gate: schematic healthcheck and netlist export must pass.
- Soft gate for early generated designs: ERC/DRC findings may exist, but should
  be collected and classified rather than confused with schematic parse failure.
