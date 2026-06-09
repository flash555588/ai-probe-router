"""Tests for CI delivery-contract signals."""

from pathlib import Path


def test_ci_shows_skips_and_has_native_kicad_gate():
    workflow = (
        Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")

    assert "pytest --tb=short -ra -q" in workflow
    assert "native-kicad:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "ghcr.io/inti-cmnb/kicad8_auto:latest" in workflow
    assert (
        "python scripts/kicad_native_validate.py "
        "examples/audio_player_project --require-kicad"
    ) in workflow
