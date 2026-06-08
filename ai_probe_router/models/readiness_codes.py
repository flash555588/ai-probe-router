"""Central readiness and verification codes across all PRs.

All issue/warning/blocker codes live here so the plugin shell and tests
can reference them without hard-coding strings in multiple places.
"""

from __future__ import annotations

from enum import Enum


class ReadinessCode(str, Enum):
    """Codes emitted by the engine and various solvers.

    Each code maps to exactly one severity when used in a readiness report.
    """

    # PR5 — Resource Allocator
    RESOURCE_ALLOCATOR_DISABLED = "RESOURCE_ALLOCATOR_DISABLED"
    BUS_ADDRESS_CONFLICT_UNRESOLVED = "BUS_ADDRESS_CONFLICT_UNRESOLVED"
    BUS_ALLOCATION_NEAR_LIMIT = "BUS_ALLOCATION_NEAR_LIMIT"
    POWER_DOMAIN_OVERLOAD = "POWER_DOMAIN_OVERLOAD"
    POWER_DOMAIN_NEAR_LIMIT = "POWER_DOMAIN_NEAR_LIMIT"

    # PR6 — Footprint Preview
    FOOTPRINT_PREVIEW_MISSING_REQUIRED_FOOTPRINT = (
        "FOOTPRINT_PREVIEW_MISSING_REQUIRED_FOOTPRINT"
    )
    FOOTPRINT_PREVIEW_COLLISION = "FOOTPRINT_PREVIEW_COLLISION"
    FOOTPRINT_PREVIEW_OUT_OF_BOUNDS = "FOOTPRINT_PREVIEW_OUT_OF_BOUNDS"
    FOOTPRINT_PREVIEW_KEEPOUT_VIOLATION = "FOOTPRINT_PREVIEW_KEEPOUT_VIOLATION"
    FOOTPRINT_PREVIEW_DENSE_REGION = "FOOTPRINT_PREVIEW_DENSE_REGION"
    FOOTPRINT_PREVIEW_CANDIDATE_ONLY = "FOOTPRINT_PREVIEW_CANDIDATE_ONLY"

    # PR3 — Pin Mapper
    CP_SAT_SOLVER_USED = "CP_SAT_SOLVER_USED"
    PIN_MAPPER_COMPARE_DIFFERENCE = "PIN_MAPPER_COMPARE_DIFFERENCE"
    ORTOOLS_MISSING_FALLBACK_TO_GREEDY = "ORTOOLS_MISSING_FALLBACK_TO_GREEDY"
    CP_SAT_REQUIRED_BUT_ORTOOLS_MISSING = "CP_SAT_REQUIRED_BUT_ORTOOLS_MISSING"
    CP_SAT_NO_FEASIBLE_MAPPING = "CP_SAT_NO_FEASIBLE_MAPPING"
    PIN_MAPPING_CONSTRAINT_CONFLICT = "PIN_MAPPING_CONSTRAINT_CONFLICT"

    # PR2 — Route Import
    ROUTE_IMPORT_UNKNOWN_NET = "ROUTE_IMPORT_UNKNOWN_NET"
    ROUTE_IMPORT_INVALID_LAYER = "ROUTE_IMPORT_INVALID_LAYER"
    ROUTE_IMPORT_INVALID_COORDINATE = "ROUTE_IMPORT_INVALID_COORDINATE"
    ROUTE_IMPORT_NET_ZERO = "ROUTE_IMPORT_NET_ZERO"
    ROUTE_IMPORT_SAFETY_PASSED = "ROUTE_IMPORT_SAFETY_PASSED"

    # PR1 / General
    MODULE_LIBRARY_PREFLIGHT_ERROR = "MODULE_LIBRARY_PREFLIGHT_ERROR"
    MODULE_GRAPH_ERROR = "MODULE_GRAPH_ERROR"
    MODULE_COMPATIBILITY_ERROR = "MODULE_COMPATIBILITY_ERROR"


_READINESS_CODE_SEVERITY: dict[ReadinessCode, str] = {
    ReadinessCode.RESOURCE_ALLOCATOR_DISABLED: "info",
    ReadinessCode.BUS_ADDRESS_CONFLICT_UNRESOLVED: "error",
    ReadinessCode.BUS_ALLOCATION_NEAR_LIMIT: "warning",
    ReadinessCode.POWER_DOMAIN_OVERLOAD: "error",
    ReadinessCode.POWER_DOMAIN_NEAR_LIMIT: "warning",
    ReadinessCode.FOOTPRINT_PREVIEW_MISSING_REQUIRED_FOOTPRINT: "error",
    ReadinessCode.FOOTPRINT_PREVIEW_COLLISION: "error",
    ReadinessCode.FOOTPRINT_PREVIEW_OUT_OF_BOUNDS: "error",
    ReadinessCode.FOOTPRINT_PREVIEW_KEEPOUT_VIOLATION: "error",
    ReadinessCode.FOOTPRINT_PREVIEW_DENSE_REGION: "warning",
    ReadinessCode.FOOTPRINT_PREVIEW_CANDIDATE_ONLY: "info",
    ReadinessCode.CP_SAT_SOLVER_USED: "warning",
    ReadinessCode.PIN_MAPPER_COMPARE_DIFFERENCE: "warning",
    ReadinessCode.ORTOOLS_MISSING_FALLBACK_TO_GREEDY: "warning",
    ReadinessCode.CP_SAT_REQUIRED_BUT_ORTOOLS_MISSING: "error",
    ReadinessCode.CP_SAT_NO_FEASIBLE_MAPPING: "error",
    ReadinessCode.PIN_MAPPING_CONSTRAINT_CONFLICT: "error",
    ReadinessCode.ROUTE_IMPORT_UNKNOWN_NET: "error",
    ReadinessCode.ROUTE_IMPORT_INVALID_LAYER: "error",
    ReadinessCode.ROUTE_IMPORT_INVALID_COORDINATE: "error",
    ReadinessCode.ROUTE_IMPORT_NET_ZERO: "error",
    ReadinessCode.ROUTE_IMPORT_SAFETY_PASSED: "info",
    ReadinessCode.MODULE_LIBRARY_PREFLIGHT_ERROR: "error",
    ReadinessCode.MODULE_GRAPH_ERROR: "error",
    ReadinessCode.MODULE_COMPATIBILITY_ERROR: "error",
}


def code_severity(code: ReadinessCode | str) -> str:
    """Return the default severity for a readiness code."""
    if isinstance(code, ReadinessCode):
        return _READINESS_CODE_SEVERITY.get(code, "warning")
    # Try to look up by string value
    try:
        enum_code = ReadinessCode(code)
        return _READINESS_CODE_SEVERITY.get(enum_code, "warning")
    except ValueError:
        return "warning"
