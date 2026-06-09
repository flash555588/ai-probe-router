# KiCad Plugin Manual Signoff

Headless CI verifies the fallback plugin code path, CLI dependency guidance, and
plugin-shell report loaders. A real KiCad desktop session is still required
before release because KiCad bundles `pcbnew` and wxPython differently from a
normal Python virtual environment.

Run this checklist on Linux or Windows with KiCad installed and the project
installed with the plugin extra:

```bash
uv pip install -e ".[dev]"
uv pip install -e ".[plugin]"
apr generate examples/sample_config.yaml -d examples/minimal_project
apr plugin-shell examples/minimal_project/output --no-3d
```

For the 3D path, run:

```bash
apr plugin-shell examples/minimal_project/output --step 3D_PCB1.step
```

Record the following evidence in the release notes or PR comment:

- KiCad version and operating system.
- `apr plugin-shell ... --no-3d` opens without an ImportError.
- The Footprint Preview, Resource Allocation, and Route Import tabs render.
- With `.[plugin]` installed, the 3D tab opens or falls back to the 2D board
  view with a visible warning when the STEP file is missing or invalid.
- Inside KiCad PCB Editor, the AI Probe Router action plugin is visible in the
  plugin menu or toolbar.
- Running the action plugin on a saved board creates an `output/` directory and
  shows a KiCad info dialog on success.
- The generated temporary config contains selected non-trivial nets and does
  not include unnamed `Net-(...)` local nets unless the user selected them in
  the wx dialog.
- On CLI failure, the plugin shows KiCad's error dialog with captured stdout or
  stderr.

For release signoff, record the same evidence in `plugin_signoff.json`:

```json
{
  "os": "Windows 11",
  "kicad_version": "8.0.0",
  "evidence_link": "https://example.invalid/release-signoff",
  "plugin_shell_no_3d_opened": true,
  "report_tabs_rendered": true,
  "three_d_view_checked": true,
  "action_plugin_visible": true,
  "action_plugin_generates_output": true,
  "temporary_config_selects_nontrivial_nets": true,
  "error_dialog_captures_cli_failure": true,
  "notes": []
}
```

Validate it with:

```bash
python scripts/plugin_signoff_validate.py plugin_signoff.json --require-signoff
```

Release wording:

```text
Headless plugin fallback tests pass in CI. Native KiCad plugin and GUI signoff
completed manually on <OS> with KiCad <version>; evidence recorded in <link>.
```
