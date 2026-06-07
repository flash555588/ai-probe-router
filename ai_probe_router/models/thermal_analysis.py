"""Thermal analysis configuration for design review and simulation export."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ThermalAnalysis:
    enabled: bool = False
    max_junction_temp_c: float = 125.0
    ambient_temp_c: float = 25.0
    output_format: str = "csv"

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "max_junction_temp_c": self.max_junction_temp_c,
            "ambient_temp_c": self.ambient_temp_c,
            "output_format": self.output_format,
        }
