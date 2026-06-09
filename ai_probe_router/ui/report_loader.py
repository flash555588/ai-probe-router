"""Load and parse JSON reports from PR2/PR5/PR6/PR8 for the plugin shell.

All functions are safe to call even when the report files are missing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FootprintEntry:
    module_name: str
    reference: str
    footprint: str
    x_mm: float
    y_mm: float
    rotation_deg: float
    side: str
    role: str | None


@dataclass
class IssueEntry:
    severity: str
    code: str
    message: str
    module_name: str | None
    reference: str | None


@dataclass
class FootprintPreviewData:
    ok: bool
    has_warnings: bool
    footprints: list[FootprintEntry]
    issues: list[IssueEntry]


@dataclass
class ResourceBusEntry:
    bus_type: str
    bus_id: int
    module: str
    instance_id: str
    address: str


@dataclass
class ResourcePowerEntry:
    domain: str
    voltage: float
    budget_ma: float
    requested_ma: float
    headroom_percent: float


@dataclass
class ResourceAllocationData:
    ok: bool
    warnings: list[str]
    errors: list[str]
    buses: list[ResourceBusEntry]
    power: list[ResourcePowerEntry]


@dataclass
class ResourceRecommendationEntry:
    recommendation_id: str
    severity: str
    category: str
    scope: str
    recommendation: str
    module_name: str
    applies_to: list[str]
    current_assignment: str
    expected_impact: str
    safe_to_apply_automatically: bool


@dataclass
class ResourceOptimizationData:
    ok: bool
    recommendations: list[ResourceRecommendationEntry]
    notes: list[str]


@dataclass
class ReadinessIssue:
    severity: str
    source: str
    message: str


@dataclass
class ReadinessData:
    verdict: str
    run_id: str
    blockers: list[ReadinessIssue]
    warnings: list[ReadinessIssue]


def load_footprint_preview(path: Path) -> FootprintPreviewData | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    footprints = [
        FootprintEntry(
            module_name=fp.get("module_name", ""),
            reference=fp.get("reference", ""),
            footprint=fp.get("footprint", ""),
            x_mm=fp.get("x_mm", 0.0),
            y_mm=fp.get("y_mm", 0.0),
            rotation_deg=fp.get("rotation_deg", 0.0),
            side=fp.get("side", "top"),
            role=fp.get("role"),
        )
        for fp in raw.get("planned_footprints", [])
    ]
    issues = [
        IssueEntry(
            severity=iss.get("severity", "info"),
            code=iss.get("code", ""),
            message=iss.get("message", ""),
            module_name=iss.get("module_name"),
            reference=iss.get("reference"),
        )
        for iss in raw.get("issues", [])
    ]
    return FootprintPreviewData(
        ok=raw.get("ok", True),
        has_warnings=raw.get("has_warnings", False),
        footprints=footprints,
        issues=issues,
    )


def load_resource_allocation(path: Path) -> ResourceAllocationData | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    buses: list[ResourceBusEntry] = []
    power: list[ResourcePowerEntry] = []

    # Try PR5 bus_result / power_result nested shape
    bus_result = raw.get("bus_result", {})
    power_result = raw.get("power_result", {})

    for b in bus_result.get("assignments", []):
        buses.append(
            ResourceBusEntry(
                bus_type=b.get("bus_type", ""),
                bus_id=b.get("bus_id", 0),
                module=b.get("module_name", ""),
                instance_id=b.get("instance_id", ""),
                address=b.get("address", ""),
            )
        )

    for d in power_result.get("domains", []):
        power.append(
            ResourcePowerEntry(
                domain=d.get("domain_name", ""),
                voltage=d.get("voltage", 0.0),
                budget_ma=d.get("budget_ma", 0.0),
                requested_ma=d.get("requested_ma", 0.0),
                headroom_percent=d.get("headroom_percent", 0.0),
            )
        )

    return ResourceAllocationData(
        ok=raw.get("ok", True),
        warnings=raw.get("warnings", []),
        errors=raw.get("errors", []),
        buses=buses,
        power=power,
    )


def load_resource_optimization(path: Path) -> ResourceOptimizationData | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    recommendations = [
        ResourceRecommendationEntry(
            recommendation_id=rec.get("recommendation_id", ""),
            severity=rec.get("severity", "info"),
            category=rec.get("category", ""),
            scope=rec.get("scope", ""),
            module_name=rec.get("module_name", ""),
            applies_to=[str(v) for v in rec.get("applies_to", [])],
            current_assignment=rec.get("current_assignment", ""),
            recommendation=rec.get("recommendation", ""),
            expected_impact=rec.get("expected_impact", ""),
            safe_to_apply_automatically=bool(
                rec.get("safe_to_apply_automatically", False)
            ),
        )
        for rec in raw.get("recommendations", [])
    ]
    return ResourceOptimizationData(
        ok=raw.get("ok", True),
        recommendations=recommendations,
        notes=[str(note) for note in raw.get("notes", [])],
    )


def load_readiness(path: Path) -> ReadinessData | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    blockers = [
        ReadinessIssue(
            severity=b.get("severity", "error"),
            source=b.get("source", ""),
            message=b.get("message", ""),
        )
        for b in raw.get("blockers", [])
    ]
    warnings = [
        ReadinessIssue(
            severity=w.get("severity", "warning"),
            source=w.get("source", ""),
            message=w.get("message", ""),
        )
        for w in raw.get("warnings", [])
    ]
    return ReadinessData(
        verdict=raw.get("verdict", "PASS"),
        run_id=raw.get("run_id", ""),
        blockers=blockers,
        warnings=warnings,
    )
