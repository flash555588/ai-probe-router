"""Advisory resource optimization recommendations.

This layer intentionally does not mutate schematics, PCB files, or project
configuration.  It converts deterministic resource-allocation pressure into
recommendations that a user or GUI can inspect before making changes.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .bus_allocator import BusAssignment
from .power_domain_solver import PowerDomainStatus
from .resource_allocator import ResourceAllocationResult


@dataclass(frozen=True)
class ResourceOptimizationRecommendation:
    recommendation_id: str
    severity: str
    category: str
    scope: str
    recommendation: str
    current_assignment: str = ""
    module_name: str = ""
    applies_to: tuple[str, ...] = ()
    expected_impact: str = ""
    safe_to_apply_automatically: bool = False


@dataclass
class ResourceOptimizationReport:
    recommendations: list[ResourceOptimizationRecommendation] = field(
        default_factory=list
    )
    schema_version: int = 1
    notes: list[str] = field(default_factory=lambda: [
        "Recommendations are advisory only; no schematic, PCB, or config mutation was performed.",
    ])

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def errors(self) -> list[ResourceOptimizationRecommendation]:
        return [rec for rec in self.recommendations if rec.severity == "error"]

    @property
    def warnings(self) -> list[ResourceOptimizationRecommendation]:
        return [rec for rec in self.recommendations if rec.severity == "warning"]

    @property
    def infos(self) -> list[ResourceOptimizationRecommendation]:
        return [rec for rec in self.recommendations if rec.severity == "info"]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "ok": self.ok,
            "summary": {
                "recommendations": len(self.recommendations),
                "errors": len(self.errors),
                "warnings": len(self.warnings),
                "infos": len(self.infos),
                "bus_recommendations": sum(
                    1 for rec in self.recommendations if rec.category == "bus"
                ),
                "power_recommendations": sum(
                    1 for rec in self.recommendations if rec.category == "power"
                ),
            },
            "recommendations": [
                {
                    "recommendation_id": rec.recommendation_id,
                    "severity": rec.severity,
                    "category": rec.category,
                    "scope": rec.scope,
                    "module_name": rec.module_name,
                    "applies_to": list(rec.applies_to),
                    "current_assignment": rec.current_assignment,
                    "recommendation": rec.recommendation,
                    "expected_impact": rec.expected_impact,
                    "safe_to_apply_automatically": rec.safe_to_apply_automatically,
                }
                for rec in self.recommendations
            ],
            "notes": self.notes,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2) + "\n"


def generate_resource_optimization_report(
    allocation: ResourceAllocationResult,
) -> ResourceOptimizationReport:
    """Generate advisory optimization recommendations from allocation state."""
    recommendations: list[ResourceOptimizationRecommendation] = []
    recommendations.extend(_power_recommendations(allocation.power_result.overload_domains))
    recommendations.extend(_power_recommendations(allocation.power_result.near_limit_domains))
    recommendations.extend(_bus_conflict_recommendations(allocation))
    recommendations.extend(_bus_pressure_recommendations(allocation))
    return ResourceOptimizationReport(recommendations=recommendations)


def write_resource_optimization_report(
    report: ResourceOptimizationReport,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "resource_optimization_report.json").write_text(
        report.to_json(),
        encoding="utf-8",
    )


def _power_recommendations(
    domains: list[PowerDomainStatus],
) -> list[ResourceOptimizationRecommendation]:
    recommendations: list[ResourceOptimizationRecommendation] = []
    for domain in domains:
        overloaded = domain.requested_ma > domain.budget_ma and domain.budget_ma > 0
        severity = "error" if overloaded else "warning"
        kind = "OVERLOAD" if overloaded else "NEAR_LIMIT"
        recommendations.append(
            ResourceOptimizationRecommendation(
                recommendation_id=f"ROPT-POWER-{kind}-{_slug(domain.domain_name)}",
                severity=severity,
                category="power",
                scope=domain.domain_name,
                current_assignment=(
                    f"domain={domain.domain_name} voltage={domain.voltage:g}V "
                    f"requested={domain.requested_ma:.1f}mA "
                    f"budget={domain.budget_ma:.1f}mA "
                    f"headroom={domain.headroom_percent:.1f}%"
                ),
                recommendation=(
                    "Increase this rail budget, add a dedicated regulator, or move "
                    "eligible load to another declared voltage domain after review."
                    if overloaded
                    else "Review this rail before layout freeze; reserve margin or move "
                    "non-critical load if more modules are added."
                ),
                expected_impact=(
                    "Restores non-negative power headroom."
                    if overloaded
                    else "Keeps late-stage module additions from turning this rail into a blocker."
                ),
            )
        )
    return recommendations


def _bus_conflict_recommendations(
    allocation: ResourceAllocationResult,
) -> list[ResourceOptimizationRecommendation]:
    recommendations: list[ResourceOptimizationRecommendation] = []
    for conflict in allocation.bus_result.conflicts:
        modules = tuple(sorted(conflict.modules))
        recommendations.append(
            ResourceOptimizationRecommendation(
                recommendation_id=(
                    f"ROPT-BUS-CONFLICT-{conflict.bus_type.upper()}-"
                    f"{_slug(conflict.address)}"
                ),
                severity="error",
                category="bus",
                scope=f"{conflict.bus_type.upper()} address {conflict.address}",
                applies_to=modules,
                current_assignment=(
                    f"{conflict.bus_type.upper()} address {conflict.address}: "
                    + ", ".join(modules)
                ),
                recommendation=(
                    "Move one conflicting device to another bus or change one device "
                    "address in the module configuration."
                ),
                expected_impact="Removes the unresolved shared-address conflict.",
            )
        )
    return recommendations


def _bus_pressure_recommendations(
    allocation: ResourceAllocationResult,
) -> list[ResourceOptimizationRecommendation]:
    groups: dict[tuple[str, int], list[BusAssignment]] = defaultdict(list)
    for assignment in allocation.bus_result.assignments:
        groups[(assignment.bus_type, assignment.bus_id)].append(assignment)

    recommendations: list[ResourceOptimizationRecommendation] = []
    max_id_by_type: dict[str, int] = {}
    for bus_type, bus_id in groups:
        max_id_by_type[bus_type] = max(max_id_by_type.get(bus_type, 0), bus_id)

    for (bus_type, bus_id), assignments in sorted(groups.items()):
        limit = _bus_pressure_limit(bus_type)
        if len(assignments) < limit:
            continue
        modules = tuple(sorted({assignment.module_name for assignment in assignments}))
        next_bus_id = max_id_by_type.get(bus_type, bus_id) + 1
        recommendations.append(
            ResourceOptimizationRecommendation(
                recommendation_id=f"ROPT-BUS-SPLIT-{bus_type.upper()}-{bus_id}",
                severity="warning",
                category="bus",
                scope=f"{bus_type.upper()}-{bus_id}",
                applies_to=modules,
                current_assignment=(
                    f"{bus_type.upper()}-{bus_id} has {len(assignments)} module(s): "
                    + ", ".join(modules)
                ),
                recommendation=(
                    f"Consider moving lower-priority modules to {bus_type.upper()}-"
                    f"{next_bus_id} and keeping timing-critical devices on "
                    f"{bus_type.upper()}-{bus_id}."
                ),
                expected_impact=(
                    "Reduces bus fanout and creates more debugging headroom without "
                    "automatic schematic mutation."
                ),
            )
        )
    return recommendations


def _bus_pressure_limit(bus_type: str) -> int:
    return 5 if bus_type == "i2c" else 4


def _slug(value: str) -> str:
    chars = [c.upper() if c.isalnum() else "_" for c in value]
    slug = "".join(chars).strip("_")
    return slug or "UNSPECIFIED"
