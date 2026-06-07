"""Impedance control rules for differential pairs and high-speed nets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DiffPairImpedance:
    target_impedance_ohm: float = 90.0
    tolerance_percent: float = 10.0
    diff_pair_width_mm: float = 0.15
    diff_pair_gap_mm: float = 0.15


@dataclass
class ImpedanceControl:
    rules: dict[str, DiffPairImpedance] = None

    def __post_init__(self):
        if self.rules is None:
            self.rules = {}

    def get_rule(self, name: str) -> DiffPairImpedance | None:
        return self.rules.get(name)

    def has_rules(self) -> bool:
        return bool(self.rules)
