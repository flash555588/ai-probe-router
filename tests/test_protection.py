"""Tests for protection circuit generation."""

from ai_probe_router.eda_adapters.kicad.sch_writer import (
    add_protected_testpoint_symbol,
    add_testpoint_symbol,
)
from ai_probe_router.models.board import Schematic
from ai_probe_router.models.protection import (
    ROLE_PROTECTION_DEFAULTS,
    ProtectionComponent,
    ProtectionRules,
    ProtectionType,
    protection_type_from_string,
)


def _make_minimal_sch() -> Schematic:
    raw = [
        "kicad_sch",
        ["version", "20230121"],
        ["lib_symbols"],
    ]
    return Schematic(raw=raw, components=[], labels=[], wires=[])


def test_protection_defaults():
    rules = ProtectionRules.with_defaults()
    assert rules.get_protection("debug") is not None
    assert rules.get_protection("reset") is not None
    assert rules.get_protection("power") is not None
    assert rules.get_protection("ground") is None
    assert rules.get_protection("communication") is None


def test_protection_disabled():
    rules = ProtectionRules(rules=dict(ROLE_PROTECTION_DEFAULTS), enabled=False)
    assert rules.get_protection("debug") is None


def test_resistor_footprint_name():
    comp = ProtectionComponent(
        protection_type=ProtectionType.SERIES_RESISTOR,
        value="33",
        package="0402",
    )
    assert "0402" in comp.footprint_name
    assert "1005" in comp.footprint_name


def test_ferrite_footprint_name():
    comp = ProtectionComponent(
        protection_type=ProtectionType.FERRITE_BEAD,
        value="600R@100MHz",
        package="0603",
    )
    assert "0603" in comp.footprint_name


def test_resistor_lib_symbol_name():
    comp = ProtectionComponent(
        protection_type=ProtectionType.SERIES_RESISTOR,
        value="33",
    )
    assert comp.lib_symbol_name == "Device:R"


def test_ferrite_lib_symbol_name():
    comp = ProtectionComponent(
        protection_type=ProtectionType.FERRITE_BEAD,
        value="600R@100MHz",
    )
    assert comp.lib_symbol_name == "Device:FerriteBead"


def test_expanded_protection_type_aliases():
    assert protection_type_from_string("esd_array") == ProtectionType.ESD_ARRAY
    assert protection_type_from_string("rc-filter") == ProtectionType.RC_FILTER
    assert protection_type_from_string("level_shifter") == ProtectionType.LEVEL_SHIFTER
    assert protection_type_from_string("current_limiter") == ProtectionType.CURRENT_LIMITER
    assert protection_type_from_string("jumper") == ProtectionType.JUMPER
    assert protection_type_from_string("resistor_array") == ProtectionType.RESISTOR_ARRAY


def test_protected_testpoint_adds_resistor_symbol():
    sch = _make_minimal_sch()
    prot = ProtectionComponent(
        protection_type=ProtectionType.SERIES_RESISTOR,
        value="33",
    )
    add_protected_testpoint_symbol(
        sch, "SWDIO", 40.0, 20.0, prot,
        tp_ref="TP1", prot_ref="R1",
    )
    symbols = [n for n in sch.raw if isinstance(n, list) and n[0] == "symbol"]
    assert len(symbols) >= 2
    labels = [n for n in sch.raw if isinstance(n, list) and n[0] == "label"]
    label_names = [n[1] for n in labels]
    assert "SWDIO" in label_names
    assert "PROBE_SWDIO" in label_names


def test_protected_testpoint_adds_ferrite_symbol():
    sch = _make_minimal_sch()
    prot = ProtectionComponent(
        protection_type=ProtectionType.FERRITE_BEAD,
        value="600R@100MHz",
        ref_prefix="FB",
    )
    add_protected_testpoint_symbol(
        sch, "3V3", 40.0, 20.0, prot,
        tp_ref="TP1", prot_ref="FB1",
    )
    lib_symbols = None
    for n in sch.raw:
        if isinstance(n, list) and n[0] == "lib_symbols":
            lib_symbols = n
            break
    assert lib_symbols is not None
    lib_ids = [
        c[1] for c in lib_symbols[1:]
        if isinstance(c, list) and c[0] == "symbol"
    ]
    assert "Device:FerriteBead" in lib_ids
    assert "Connector:TestPoint" in lib_ids


def test_protected_testpoint_wires():
    sch = _make_minimal_sch()
    prot = ProtectionComponent(
        protection_type=ProtectionType.SERIES_RESISTOR,
        value="100",
    )
    add_protected_testpoint_symbol(
        sch, "NRST", 40.0, 20.0, prot,
        tp_ref="TP1", prot_ref="R1",
    )
    wires = [n for n in sch.raw if isinstance(n, list) and n[0] == "wire"]
    assert len(wires) >= 3


def test_unprotected_testpoint_no_probe_prefix():
    sch = _make_minimal_sch()
    add_testpoint_symbol(sch, "GND", 40.0, 20.0, ref="TP1")
    labels = [n for n in sch.raw if isinstance(n, list) and n[0] == "label"]
    label_names = [n[1] for n in labels]
    assert "GND" in label_names
    assert "PROBE_GND" not in label_names
