"""Tests for schematic parser and writer."""


from ai_probe_router.eda_adapters.kicad.sch_parser import parse_schematic
from ai_probe_router.eda_adapters.kicad.sch_writer import (
    add_connector_symbol,
    add_testpoint_symbol,
    write_schematic,
)
from ai_probe_router.solvers.pin_mapper import PinAssignment

MINIMAL_SCH = """\
(kicad_sch
  (version 20231120)
  (generator "eeschema")
  (uuid "a1b2c3d4-e5f6-7890-abcd-ef1234567890")
  (paper "A4")
  (lib_symbols
    (symbol "MCU_ST_STM32F1:STM32F103C8Tx"
      (in_bom yes)
      (on_board yes)
      (property "Reference" "U"
        (at -10.16 13.97 0)
        (effects (font (size 1.27 1.27)))
      )
      (property "Value" "STM32F103C8Tx"
        (at 0 0 0)
        (effects (font (size 1.27 1.27)))
      )
    )
  )
  (symbol
    (lib_id "MCU_ST_STM32F1:STM32F103C8Tx")
    (at 100 100 0)
    (unit 1)
    (in_bom yes)
    (on_board yes)
    (uuid "abc-123")
    (property "Reference" "U1"
      (at 88.9 113.97 0)
      (effects (font (size 1.27 1.27)))
    )
    (property "Value" "STM32F103C8Tx"
      (at 88.9 111.43 0)
      (effects (font (size 1.27 1.27)))
    )
  )
  (global_label "SWDIO" (shape input)
    (at 120 96.52 0)
    (effects (font (size 1.27 1.27)))
  )
  (global_label "GND" (shape input)
    (at 130 90 0)
    (effects (font (size 1.27 1.27)))
  )
  (wire (pts (xy 112.7 96.52) (xy 120 96.52)))
)
"""


def test_parse_schematic(tmp_path):
    sch_file = tmp_path / "test.kicad_sch"
    sch_file.write_text(MINIMAL_SCH)
    sch = parse_schematic(sch_file)
    assert len(sch.components) == 1
    assert sch.components[0].ref == "U1"
    assert len(sch.labels) == 2
    assert {"SWDIO", "GND"} == {lb["name"] for lb in sch.labels}
    assert len(sch.wires) == 1


def test_parse_schematic_labels(tmp_path):
    sch_file = tmp_path / "test.kicad_sch"
    sch_file.write_text(MINIMAL_SCH)
    sch = parse_schematic(sch_file)
    swdio = next(lb for lb in sch.labels if lb["name"] == "SWDIO")
    assert swdio["type"] == "global_label"
    assert abs(swdio["x"] - 120.0) < 0.01
    assert abs(swdio["y"] - 96.52) < 0.01


def test_net_names(tmp_path):
    sch_file = tmp_path / "test.kicad_sch"
    sch_file.write_text(MINIMAL_SCH)
    sch = parse_schematic(sch_file)
    assert sch.net_names() == {"SWDIO", "GND"}


def test_add_testpoint_symbol(tmp_path):
    sch_file = tmp_path / "test.kicad_sch"
    sch_file.write_text(MINIMAL_SCH)
    sch = parse_schematic(sch_file)
    add_testpoint_symbol(sch, "SWDIO", 130, 96.52, ref="TP1")
    out = tmp_path / "out.kicad_sch"
    write_schematic(sch, out)
    text = out.read_text()
    assert "TP1" in text
    assert "TP_SWDIO" in text
    sch2 = parse_schematic(out)
    assert len(sch2.components) >= 2


def test_add_connector_symbol(tmp_path):
    sch_file = tmp_path / "test.kicad_sch"
    sch_file.write_text(MINIMAL_SCH)
    sch = parse_schematic(sch_file)
    assignments = [
        PinAssignment(net_name="SWDIO", pin_name="PA13", pin_index=0),
        PinAssignment(net_name="GND", pin_name="GND_1", pin_index=1),
    ]
    add_connector_symbol(sch, assignments, ref="J1")
    out = tmp_path / "out.kicad_sch"
    write_schematic(sch, out)
    text = out.read_text()
    assert "J1" in text
    assert "SWDIO" in text
    assert "GND" in text


def test_roundtrip_preserves_structure(tmp_path):
    sch_file = tmp_path / "test.kicad_sch"
    sch_file.write_text(MINIMAL_SCH)
    sch = parse_schematic(sch_file)
    out = tmp_path / "out.kicad_sch"
    write_schematic(sch, out)
    sch2 = parse_schematic(out)
    assert len(sch2.components) == len(sch.components)
    assert len(sch2.labels) == len(sch.labels)
