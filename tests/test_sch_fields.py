"""Tests for schematic symbol metadata fields."""

from __future__ import annotations

from pathlib import Path

from ai_probe_router.eda_adapters.kicad.sch_parser import parse_schematic
from ai_probe_router.eda_adapters.kicad.sch_writer import (
    add_protected_testpoint_symbol,
    add_testpoint_symbol,
    write_schematic,
)
from ai_probe_router.models.board import Schematic
from ai_probe_router.models.protection import ProtectionComponent, ProtectionType

MINIMAL_SCH = """\
(kicad_sch
  (version 20231120)
  (generator "test")
  (uuid "root")
  (paper "A4")
)
"""


def _collect_properties(raw: list) -> set[str]:
    names: set[str] = set()
    for node in raw:
        if isinstance(node, list):
            if node[0] == "property":
                names.add(node[1])
            else:
                names |= _collect_properties(node)
    return names


def test_testpoint_symbol_has_probe_fields(tmp_path: Path):
    sch = parse_schematic_string(MINIMAL_SCH)
    add_testpoint_symbol(
        sch, "SWDIO", 10, 20, ref="TP1",
        role="debug", required=True, current_ma=10, side="bottom",
    )
    names = _collect_properties(sch.raw)
    assert "PROBE_ROLE" in names
    assert "TEST_REQUIRED" in names
    assert "CURRENT_LIMIT" in names
    assert "ACCESS_SIDE" in names


def test_protected_testpoint_symbol_has_probe_fields(tmp_path: Path):
    sch = parse_schematic_string(MINIMAL_SCH)
    prot = ProtectionComponent(
        protection_type=ProtectionType.SERIES_RESISTOR,
        value="33",
        package="0402",
    )
    add_protected_testpoint_symbol(
        sch, "NRST", 10, 20, prot, tp_ref="TP2", prot_ref="R1",
        role="reset", required=True, current_ma=0, side="top",
    )
    names = _collect_properties(sch.raw)
    assert "PROBE_ROLE" in names
    assert "TEST_REQUIRED" in names
    assert "ACCESS_SIDE" in names


def test_roundtrip_preserved_fields(tmp_path: Path):
    sch = parse_schematic_string(MINIMAL_SCH)
    add_testpoint_symbol(
        sch, "UART_TX", 5, 5, ref="TP3",
        role="communication", required=False, side="top",
    )
    out = tmp_path / "out.kicad_sch"
    write_schematic(sch, out)
    text = out.read_text()
    assert "PROBE_ROLE" in text
    assert "communication" in text


def test_generated_probe_fields_are_quoted_and_after_uuid(tmp_path: Path):
    sch = parse_schematic_string(MINIMAL_SCH)
    add_testpoint_symbol(
        sch, "UART_TX", 5, 5, ref="TP3",
        role="communication", required=False, side="top",
    )
    symbol = next(
        n
        for n in sch.raw
        if isinstance(n, list)
        and n[0] == "symbol"
        and any(isinstance(c, list) and c[:2] == ["lib_id", "Connector:TestPoint"] for c in n)
    )
    uuid_index = next(i for i, c in enumerate(symbol) if isinstance(c, list) and c[0] == "uuid")
    probe_field_index = next(
        i
        for i, c in enumerate(symbol)
        if isinstance(c, list) and c[:2] == ["property", "PROBE_ROLE"]
    )
    assert uuid_index < probe_field_index

    out = tmp_path / "out.kicad_sch"
    write_schematic(sch, out)
    text = out.read_text()
    assert '(property "PROBE_ROLE" "communication"' in text
    assert '(property "TEST_REQUIRED" "no"' in text
    assert '(property "ACCESS_SIDE" "top"' in text
    assert '(label "UART_TX"' in text


def test_write_schematic_adds_kicad_instance_metadata(tmp_path: Path):
    sch = parse_schematic_string(MINIMAL_SCH)
    add_testpoint_symbol(sch, "UART_TX", 5, 5, ref="TP3")
    out = tmp_path / "out.kicad_sch"
    write_schematic(sch, out)

    text = out.read_text(encoding="utf-8")
    assert '(generator "ai-probe-router")' in text
    assert "(instances" in text
    assert "(sheet_instances" in text

    reparsed = parse_schematic(out)
    assert reparsed.components[0].uuid


def parse_schematic_string(text: str) -> Schematic:
    from ai_probe_router.eda_adapters.kicad.sexpr import parse
    tree = parse(text)
    return Schematic(raw=tree)
