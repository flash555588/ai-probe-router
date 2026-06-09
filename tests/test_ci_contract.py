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
    assert 'uv pip install -e ".[dev]" --system' in workflow
    assert "pip-audit --progress-spinner off" in workflow
    assert "native-kicad:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "ghcr.io/inti-cmnb/kicad8_auto:latest" in workflow
    assert (
        "python scripts/kicad_native_validate.py "
        "examples/audio_player_project --require-kicad"
    ) in workflow
    assert "if: always()" in workflow
    assert "name: native-kicad-reports" in workflow
    assert "path: examples/audio_player_project/build/kicad/" in workflow
    assert "if-no-files-found: warn" in workflow
