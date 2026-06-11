"""Tests for CI delivery-contract signals."""

from pathlib import Path


def test_ci_shows_skips_and_has_native_kicad_gate():
    workflow = (
        Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")

    assert "pytest --tb=short -ra -q" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "actions/checkout@v6" in workflow
    assert "actions/setup-python@v6" in workflow
    assert "astral-sh/setup-uv@v8.2.0" in workflow
    assert "actions/checkout@v4" not in workflow
    assert "actions/setup-python@v5" not in workflow
    assert "astral-sh/setup-uv@v4" not in workflow
    assert "actions/upload-artifact@v6" in workflow
    assert "dependency-audit:" in workflow
    assert 'uv pip install -e ".[dev]" --system --locked' in workflow
    assert "pip-audit --progress-spinner off" in workflow
    assert "native-kicad:" in workflow
    native_job = workflow.split("native-kicad:", 1)[1]
    assert "if: github.event_name == 'push'" not in native_job
    assert "workflow_dispatch:" in workflow
    assert "ghcr.io/inti-cmnb/kicad9_auto:1.8.5" in workflow
    assert "kicad8_auto:latest" not in workflow
    assert "kicad9_auto:latest" not in workflow
    assert "continue-on-error: true" in native_job
    assert "--report-dir \"$PWD/validation/reports/audio\"" in workflow
    assert "--report-dir \"$PWD/validation/reports/smoke\"" in workflow
    assert (
        "--baseline \"$PWD/examples/audio_player_project/ci/native-baseline.kicad9.json\""
        in workflow
    )
    assert "--block-new-regressions" in workflow
    smoke_step = workflow.split("Validate generated native sample", 1)[1]
    smoke_step = smoke_step.split("Verify native report artifacts", 1)[0]
    assert "--baseline" not in smoke_step
    assert "--block-new-regressions" not in smoke_step
    assert "--require-kicad" in workflow
    assert "--strict" in workflow
    assert "--exit-code-violations" in (
        Path(__file__).parent.parent
        / "ai_probe_router"
        / "verification"
        / "native_validation_runner.py"
    ).read_text(encoding="utf-8")
    assert "--schematic-parity" in (
        Path(__file__).parent.parent
        / "ai_probe_router"
        / "verification"
        / "native_validation_runner.py"
    ).read_text(encoding="utf-8")
    assert "Generate strict native sample" in workflow
    assert "apr generate /tmp/apr-native-smoke/config.yaml" in workflow
    assert "-d /tmp/apr-native-smoke" in workflow
    assert "strict_signoff: true" in workflow
    assert "require_manufacturing_exports: true" in workflow
    assert "Validate generated native sample" in workflow
    assert "/tmp/apr-native-smoke/output" in workflow
    assert "Verify native report artifacts" in workflow
    assert "validation/reports/audio/summary.json" in workflow
    assert "validation/reports/audio/artifact_manifest.json" in workflow
    assert "if: always()" in workflow
    assert "name: native-validation-reports" in workflow
    assert "path: validation/reports/**" in workflow
    assert "if-no-files-found: error" in workflow
    assert "examples/audio_player_project/build/kicad/" not in workflow
    assert "/tmp/apr-native-smoke/output/build/kicad/" not in workflow
    assert "Fail on native validation result" in workflow
