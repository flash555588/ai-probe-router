"""Models for module footprint preview."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FootprintPreviewSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class PlannedFootprint:
    module_name: str
    reference: str
    footprint: str
    x_mm: float
    y_mm: float
    rotation_deg: float = 0.0
    side: str = "top"
    role: str | None = None


@dataclass(frozen=True)
class FootprintPreviewIssue:
    severity: FootprintPreviewSeverity
    code: str
    message: str
    module_name: str | None = None
    reference: str | None = None


@dataclass
class FootprintPreviewResult:
    planned_footprints: list[PlannedFootprint] = field(default_factory=list)
    issues: list[FootprintPreviewIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(
            issue.severity == FootprintPreviewSeverity.ERROR
            for issue in self.issues
        )

    @property
    def has_warnings(self) -> bool:
        return any(
            issue.severity == FootprintPreviewSeverity.WARNING
            for issue in self.issues
        )
