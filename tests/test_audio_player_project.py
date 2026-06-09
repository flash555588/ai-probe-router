"""Tests for the audio player example project."""

from __future__ import annotations

from pathlib import Path

import yaml


def test_audio_config_uses_valid_spi_quad_interface():
    repo_root = Path(__file__).parent.parent
    config = yaml.safe_load(
        (repo_root / "examples" / "audio_player_project" / "audio_player_config.yaml")
        .read_text(encoding="utf-8")
    )
    flash = next(m for m in config["functional_modules"] if m["name"] == "flash_storage")

    assert flash["params"]["interface"] == "spi_quad"


def test_audio_regions_are_not_real_keepouts():
    from examples.audio_player_project.generate_constraints import generate_full_pcb_skeleton

    text = generate_full_pcb_skeleton()

    isolation = _zone_block(text, "Isolation_Gap")

    assert '(gr_text "Digital_Region"' in text
    assert '(gr_text "Analog_Region"' in text
    assert '(name "Digital_Region")' not in text
    assert '(name "Analog_Region")' not in text
    assert "(keepout" in isolation


def _zone_block(text: str, name: str) -> str:
    marker = f'(name "{name}")'
    marker_index = text.index(marker)
    start = text.rfind("  (zone", 0, marker_index)
    end = text.find("\n  (zone", marker_index)
    if end == -1:
        end = text.find("\n  (gr_rect", marker_index)
    return text[start:end]
