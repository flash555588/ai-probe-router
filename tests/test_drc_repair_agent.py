"""Tests for the DRC repair agent."""

from __future__ import annotations

from ai_probe_router.ai.drc_repair_agent import RepairReport, suggest_fixes


def test_suggest_fixes_empty():
    report = suggest_fixes([])
    assert isinstance(report, RepairReport)
    assert len(report.suggestions) == 0


def test_clearance_violation():
    v = [{"type": "clearance", "description": "pad-pad clearance < 0.15mm", "net": "SIG1"}]
    report = suggest_fixes(v)
    assert len(report.suggestions) == 1
    s = report.suggestions[0]
    assert s.confidence == "high"
    assert "clearance" in s.suggested_action.lower()


def test_unconnected_pin():
    v = [{"type": "unconnected", "description": "Pin 1 has no net", "net": ""}]
    report = suggest_fixes(v)
    s = report.suggestions[0]
    assert s.auto_applicable
    assert "net label" in s.suggested_action.lower()


def test_power_short_low_confidence():
    v = [{"type": "short", "description": "Short between GND and 3V3", "net": "GND"}]
    report = suggest_fixes(v)
    s = report.suggestions[0]
    assert s.confidence == "low"
    assert "net ties" in s.suggested_action.lower()


def test_summary_format():
    v = [{"type": "silk", "description": "Silk over pad", "net": ""}]
    report = suggest_fixes(v)
    text = report.summary()
    assert "Repair Suggestions" in text
    assert "silk" in text.lower()
