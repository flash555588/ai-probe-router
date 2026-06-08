"""Tests for KiCad schematic healthcheck and repair."""

from __future__ import annotations

from pathlib import Path

from ai_probe_router.eda_adapters.kicad.sch_health import (
    healthcheck_schematic,
    repair_schematic_file,
)


def test_audio_player_schematic_healthcheck_detects_placeholder_metadata(tmp_path: Path):
    schematic = tmp_path / "main.kicad_sch"
    schematic.write_text(BROKEN_AUDIO_SNIPPET, encoding="utf-8")

    report = healthcheck_schematic(schematic)

    assert report.balanced_sexpr
    assert report.invalid_uuid_count > 0
    assert report.quoted_uuid_count > 0
    assert report.schematic_symbol_instances < report.schematic_symbol_count
    assert not report.has_sheet_instances
    assert not report.ok


def test_audio_player_schematic_repair_produces_kicad_safe_metadata(tmp_path: Path):
    broken = tmp_path / "main.kicad_sch"
    repaired = tmp_path / "main_repaired.kicad_sch"
    broken.write_text(BROKEN_AUDIO_SNIPPET, encoding="utf-8")

    repair_schematic_file(broken, repaired)
    report = healthcheck_schematic(repaired)
    text = repaired.read_text(encoding="utf-8")

    assert report.ok
    assert '(generator "ai-probe-router")' in text
    assert "(sheet_instances" in text
    assert '(path "/"' in text
    assert '(page "1")' in text


BROKEN_AUDIO_SNIPPET = """\
(kicad_sch
  (version 20231120)
  (generator "eeschema")
  (generator_version "8.0")
  (uuid "a1b2c3d4-1111-2222-3333-444444444444")
  (paper "A4")
  (lib_symbols
    (symbol "Device:R"
      (in_bom yes)
      (on_board yes)
      (property "Reference" "R" (at 0 0 0) (effects (font (size 1.27 1.27))))
      (property "Value" "R" (at 0 0 0) (effects (font (size 1.27 1.27))))
    )
  )
  (symbol
    (lib_id "Device:R")
    (at 10 10 0)
    (unit 1)
    (exclude_from_sim no)
    (in_bom yes)
    (on_board yes)
    (dnp no)
    (uuid "r1000000-0000-0000-0000-000000000001")
    (property "Reference" "R1" (at 10 10 0) (effects (font (size 1.27 1.27))))
    (property "Value" "10k" (at 10 12 0) (effects (font (size 1.27 1.27))))
    (pin "1" (uuid "r1p00001-0000-0000-0000-000000000001"))
  )
)
"""
