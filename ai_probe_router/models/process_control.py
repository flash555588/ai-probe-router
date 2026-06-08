"""Process-control models for signoff gaps, waivers, and traceability."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProcessWaiver:
    waiver_id: str
    issue_id: str
    source: str = ""
    reason: str = ""
    owner: str = ""
    expires_on: str = ""

    @property
    def complete(self) -> bool:
        return bool(self.waiver_id and self.issue_id and self.reason and self.owner)


@dataclass
class ProcessControls:
    waivers: list[ProcessWaiver] = field(default_factory=list)
    strict_signoff: bool = False
    require_autorouter_feedback: bool = False
    require_manufacturing_exports: bool = False
    scalability_module_warning_threshold: int = 20
    scalability_net_warning_threshold: int = 200
    params: dict[str, Any] = field(default_factory=dict)
