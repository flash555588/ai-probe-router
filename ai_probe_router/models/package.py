from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PackageOption:
    name: str
    footprint: str = ""
    area_mm2: float = 0.0

