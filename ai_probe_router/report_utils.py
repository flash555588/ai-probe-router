"""Unified report reader for all ai-probe-router output artifacts.

Consumes JSON/text reports produced by PR2–PR6 and exposes them through a
single interface.  Safe to call when files are missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .ui.report_loader import (
    FootprintPreviewData,
    ReadinessData,
    ResourceAllocationData,
    load_footprint_preview,
    load_readiness,
    load_resource_allocation,
)


@dataclass
class UnifiedReports:
    """All available reports from an output directory."""

    output_dir: Path
    footprint_preview: FootprintPreviewData | None = None
    resource_allocation: ResourceAllocationData | None = None
    readiness: ReadinessData | None = None

    @property
    def has_any(self) -> bool:
        return any(
            (self.footprint_preview, self.resource_allocation, self.readiness)
        )

    @property
    def all_ok(self) -> bool:
        """True when every loaded report is ok (no blockers)."""
        return all(
            r is None or r.ok
            for r in (
                self.footprint_preview,
                self.resource_allocation,
            )
        ) and (self.readiness is None or self.readiness.verdict != "BLOCKED")

    @property
    def total_blockers(self) -> int:
        count = 0
        if self.footprint_preview:
            count += sum(
                1 for i in self.footprint_preview.issues if i.severity == "error"
            )
        if self.resource_allocation:
            count += len(self.resource_allocation.errors)
        if self.readiness:
            count += len(self.readiness.blockers)
        return count

    @property
    def total_warnings(self) -> int:
        count = 0
        if self.footprint_preview:
            count += sum(
                1 for i in self.footprint_preview.issues if i.severity == "warning"
            )
        if self.resource_allocation:
            count += len(self.resource_allocation.warnings)
        if self.readiness:
            count += len(self.readiness.warnings)
        return count


def load_all_reports(output_dir: str | Path) -> UnifiedReports:
    """Load every known report from *output_dir*.

    Missing files are silently ignored so the caller can decide what to do.
    """
    out = Path(output_dir)
    return UnifiedReports(
        output_dir=out,
        footprint_preview=load_footprint_preview(
            out / "footprint_preview_report.json"
        ),
        resource_allocation=load_resource_allocation(
            out / "resource_allocation_report.json"
        ),
        readiness=load_readiness(out / "readiness_report.json"),
    )
