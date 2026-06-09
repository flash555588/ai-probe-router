"""Tests for documented KiCad plugin release signoff expectations."""

from pathlib import Path


def test_plugin_manual_signoff_checklist_documents_native_evidence():
    repo_root = Path(__file__).parent.parent
    checklist = (
        repo_root / "docs" / "kicad_plugin_manual_signoff.md"
    ).read_text(encoding="utf-8")
    plugin_docs = (repo_root / "docs" / "kicad_plugin_shell.md").read_text(
        encoding="utf-8",
    )

    assert "uv pip install -e \".[plugin]\"" in checklist
    assert "apr plugin-shell examples/minimal_project/output --no-3d" in checklist
    assert "KiCad version and operating system" in checklist
    assert "Footprint Preview, Resource Allocation, and Route Import tabs render" in checklist
    assert "AI Probe Router action plugin is visible" in checklist
    assert "Running the action plugin on a saved board creates an `output/` directory" in checklist
    assert "captured stdout or\n  stderr" in checklist
    assert "Headless plugin fallback tests pass in CI" in checklist
    assert "kicad_plugin_manual_signoff.md" in plugin_docs
