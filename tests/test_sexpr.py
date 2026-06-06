"""Tests for s-expression parser."""

from ai_probe_router.eda_adapters.kicad.sexpr import parse, serialize


def test_parse_atom():
    assert parse("hello") == "hello"


def test_parse_simple_list():
    result = parse("(version 20230121)")
    assert result == ["version", "20230121"]


def test_parse_nested():
    result = parse("(a (b c) d)")
    assert result == ["a", ["b", "c"], "d"]


def test_parse_quoted_string():
    result = parse('(net 1 "GND")')
    assert result == ["net", "1", "GND"]


def test_parse_quoted_with_spaces():
    result = parse('(property "Reference" "U1")')
    assert result == ["property", "Reference", "U1"]


def test_roundtrip_simple():
    expr = ["net", "1", "GND"]
    text = serialize(expr)
    reparsed = parse(text)
    assert reparsed == expr


def test_roundtrip_nested():
    expr = ["footprint", "TestPoint:TestPoint_Pad_D1.5mm",
            ["at", "10.0", "20.0"],
            ["pad", "1", "smd", "circle",
             ["size", "1.5", "1.5"],
             ["net", "3", "SWDIO"]]]
    text = serialize(expr)
    reparsed = parse(text)
    assert reparsed == expr


def test_empty_list():
    result = parse("()")
    assert result == []


def test_serialize_quoting():
    text = serialize(["property", "Reference", "My Component"])
    assert '"My Component"' in text
