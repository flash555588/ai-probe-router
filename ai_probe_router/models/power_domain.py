from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PowerDomain:
    name: str
    voltage: float = 0.0
    max_current_ma: float = 0.0
    voltage_min: float = 0.0
    voltage_max: float = 0.0
    current_typ_ma: float = 0.0

    def accepts_voltage(self, voltage: float) -> bool:
        if self.voltage_min == 0.0 and self.voltage_max == 0.0:
            return self.voltage == 0.0 or abs(self.voltage - voltage) < 1e-9
        return self.voltage_min <= voltage <= self.voltage_max

