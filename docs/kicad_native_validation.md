# Native KiCad Validation

PR6 adds a project-level schematic healthcheck that validates generated KiCad
schematic structure without requiring KiCad to be installed. Native KiCad
validation is still the final production gate when `kicad-cli` is available.

Run the optional wrapper from the repository root:

```bash
python scripts/kicad_native_validate.py examples/audio_player_project
```

By default, the wrapper skips gracefully when `kicad-cli` is missing. For
release CI where KiCad is installed and required:

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

Interpretation:

- Hard gate: schematic healthcheck and netlist export must pass.
- Soft gate for early generated designs: ERC/DRC findings may exist, but should
  be collected and classified rather than confused with schematic parse failure.
