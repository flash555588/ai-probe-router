"""End-to-end test with a minimal KiCad PCB."""


from ai_probe_router.eda_adapters.kicad.pcb_parser import parse_pcb
from ai_probe_router.eda_adapters.kicad.pcb_writer import add_testpoint_footprint, write_pcb

MINIMAL_PCB = """\
(kicad_pcb
  (version 20240108)
  (generator "test")
  (general (thickness 1.6))
  (paper "A4")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user "B.Mask")
    (39 "F.Mask" user "F.Mask")
    (44 "Edge.Cuts" user))
  (net 0 "")
  (net 1 "GND")
  (net 2 "3V3")
  (net 3 "SWDIO")
  (footprint "Package_QFP:LQFP-48"
    (layer "F.Cu")
    (at 100 100)
    (uuid "abc-123")
    (property "Reference" "U1")
    (property "Value" "STM32")
    (pad "1" smd rect
      (at -5.0 -3.5)
      (size 1.2 0.5)
      (layers "F.Cu" "F.Mask")
      (net 3 "SWDIO"))
    (pad "24" smd rect
      (at 0 -5.0)
      (size 0.5 1.2)
      (layers "F.Cu" "F.Mask")
      (net 1 "GND"))
    (pad "48" smd rect
      (at -5.0 3.5)
      (size 1.2 0.5)
      (layers "F.Cu" "F.Mask")
      (net 2 "3V3")))
)
"""


def test_parse_minimal_pcb(tmp_path):
    pcb_file = tmp_path / "test.kicad_pcb"
    pcb_file.write_text(MINIMAL_PCB)
    board = parse_pcb(pcb_file)
    assert "GND" in board.nets
    assert "3V3" in board.nets
    assert "SWDIO" in board.nets
    assert len(board.footprints) == 1
    assert board.footprints[0].ref == "U1"
    assert len(board.footprints[0].pads) == 3


def test_add_testpoint_and_write(tmp_path):
    pcb_file = tmp_path / "test.kicad_pcb"
    pcb_file.write_text(MINIMAL_PCB)
    board = parse_pcb(pcb_file)
    add_testpoint_footprint(board, "SWDIO", 110, 100, ref="TP1", pad_diameter=1.5)
    out_file = tmp_path / "test_out.kicad_pcb"
    write_pcb(board, out_file)
    text = out_file.read_text()
    assert "TP1" in text
    assert "SWDIO" in text
    board2 = parse_pcb(out_file)
    tp_fps = [fp for fp in board2.footprints if fp.ref == "TP1"]
    assert len(tp_fps) == 1


def test_pad_positions(tmp_path):
    pcb_file = tmp_path / "test.kicad_pcb"
    pcb_file.write_text(MINIMAL_PCB)
    board = parse_pcb(pcb_file)
    pads = board.find_pads_by_net("SWDIO")
    assert len(pads) == 1
    fp, pad = pads[0]
    assert abs(pad.x - 95.0) < 0.01
    assert abs(pad.y - 96.5) < 0.01
