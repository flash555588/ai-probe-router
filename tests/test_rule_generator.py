"""Tests for the AI rule generator."""

from __future__ import annotations

from ai_probe_router.ai.rule_generator import (
    generate_rules,
    to_kicad_design_rules,
)
from ai_probe_router.models.net import NetRole
from ai_probe_router.models.probe import ProbeRequirement


def test_generate_rules_basic():
    roles = {
        "GND": NetRole.GROUND,
        "3V3": NetRole.POWER,
        "SWDIO": NetRole.DEBUG,
        "USB_DP": NetRole.HIGH_SPEED,
    }
    rules = generate_rules(roles)
    assert len(rules.net_rules) == 4
    assert rules.review_gates
    assert any("USB_DP" in g for g in rules.review_gates)


def test_generate_rules_with_requirements():
    roles = {"MOTOR": NetRole.POWER}
    reqs = [ProbeRequirement(net_name="MOTOR", current_ma=800)]
    rules = generate_rules(roles, reqs)
    motor = next(r for r in rules.net_rules if r.net_name == "MOTOR")
    assert motor.trace_width_mm >= 0.4
    assert motor.require_human_review
    assert "high current" in motor.review_reason


def test_power_ground_defaults():
    roles = {"GND": NetRole.GROUND, "5V": NetRole.POWER}
    rules = generate_rules(roles)
    gnd = next(r for r in rules.net_rules if r.net_name == "GND")
    pwr = next(r for r in rules.net_rules if r.net_name == "5V")
    assert gnd.duplicate_probe_count >= 2
    assert pwr.duplicate_probe_count >= 1
    assert gnd.allow_shared_contacts
    assert pwr.allow_shared_contacts


def test_to_kicad_design_rules():
    roles = {"USB_DP": NetRole.HIGH_SPEED}
    rules = generate_rules(roles)
    kicad = to_kicad_design_rules(rules)
    assert len(kicad) == 1
    assert kicad[0]["name"] == "NET_USB_DP"
    assert kicad[0]["diff_pair_width"] is not None


def test_summary_output():
    roles = {"CLK": NetRole.CLOCK}
    rules = generate_rules(roles)
    text = rules.summary()
    assert "CLK" in text
    assert "REVIEW REQUIRED" in text
