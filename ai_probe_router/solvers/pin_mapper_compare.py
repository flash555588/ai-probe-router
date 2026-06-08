"""Compare greedy and CP-SAT pin mapper results."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..models.dev_board import DevelopmentBoard
from ..models.probe import ProbeRequirement
from .pin_mapper import MappingResult, solve_mapping
from .pin_mapper_cp_sat import map_pins_cp_sat, ortools_available


@dataclass
class PinMapperDifference:
    net_name: str
    greedy_pin: str = ""
    cp_sat_pin: str = ""


@dataclass
class PinMapperCompareReport:
    greedy_result: MappingResult
    cp_sat_result: MappingResult
    selected_output: str = "greedy"
    warnings: list[str] = field(default_factory=list)
    differences: list[PinMapperDifference] = field(default_factory=list)

    @property
    def selected_result(self) -> MappingResult:
        if self.selected_output == "cp_sat":
            return self.cp_sat_result
        return self.greedy_result

    def to_dict(self) -> dict:
        return {
            "selected_output": self.selected_output,
            "same_assignments": not self.differences,
            "different_assignments": [
                {
                    "net_name": diff.net_name,
                    "greedy_pin": diff.greedy_pin,
                    "cp_sat_pin": diff.cp_sat_pin,
                }
                for diff in self.differences
            ],
            "greedy": _result_dict(self.greedy_result),
            "cp_sat": _result_dict(self.cp_sat_result),
            "warnings": self.warnings,
        }

    def summary_text(self) -> str:
        lines = [
            "=" * 96,
            "  AI Probe Router - Pin Mapper Compare Report",
            "=" * 96,
            "",
            f"  Selected output:  {self.selected_output}",
            f"  Greedy score:     {self.greedy_result.objective_score:.1f}",
            f"  CP-SAT score:     {self.cp_sat_result.objective_score:.1f}",
            f"  Differences:      {len(self.differences)}",
            "",
        ]
        if self.warnings:
            lines.append("  Warnings:")
            for warning in self.warnings:
                lines.append(f"    - {warning}")
            lines.append("")
        if self.differences:
            lines.append("  Assignment Differences:")
            for diff in self.differences:
                lines.append(
                    f"    - {diff.net_name}: greedy={diff.greedy_pin or 'unmapped'}, "
                    f"cp_sat={diff.cp_sat_pin or 'unmapped'}"
                )
        else:
            lines.append("  Assignments match.")
        lines.append("")
        lines.append("=" * 96)
        return "\n".join(lines)

    def write(self, text_path: str | Path, json_path: str | Path) -> None:
        Path(text_path).write_text(self.summary_text(), encoding="utf-8")
        Path(json_path).write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def compare_pin_mappers(
    requirements: list[ProbeRequirement],
    development_board: DevelopmentBoard,
    *,
    weights: Any = None,
    selected_output: str = "greedy",
) -> PinMapperCompareReport:
    greedy = solve_mapping(requirements, development_board)
    greedy.objective_score = sum(assignment.score for assignment in greedy.assignments)
    if not ortools_available():
        cp_sat = MappingResult(
            errors=["CP_SAT_REQUIRED_BUT_ORTOOLS_MISSING"],
            solver="cp_sat",
        )
        warnings = ["ORTOOLS_MISSING_FALLBACK_TO_GREEDY"]
        selected_output = "greedy"
    else:
        cp_sat = map_pins_cp_sat(requirements, development_board, weights=weights)
        warnings = []
    differences = _differences(greedy, cp_sat)
    if differences:
        warnings.append("PIN_MAPPER_COMPARE_DIFFERENCE")
    return PinMapperCompareReport(
        greedy_result=greedy,
        cp_sat_result=cp_sat,
        selected_output=selected_output,
        warnings=warnings,
        differences=differences,
    )


def _differences(
    greedy: MappingResult,
    cp_sat: MappingResult,
) -> list[PinMapperDifference]:
    greedy_map = _assignment_map(greedy)
    cp_sat_map = _assignment_map(cp_sat)
    differences: list[PinMapperDifference] = []
    for net_name in sorted(set(greedy_map) | set(cp_sat_map)):
        greedy_pin = greedy_map.get(net_name, "")
        cp_sat_pin = cp_sat_map.get(net_name, "")
        if greedy_pin != cp_sat_pin:
            differences.append(PinMapperDifference(net_name, greedy_pin, cp_sat_pin))
    return differences


def _assignment_map(result: MappingResult) -> dict[str, str]:
    rows: dict[str, list[str]] = {}
    for assignment in result.assignments:
        rows.setdefault(assignment.net_name, []).append(assignment.pin_name)
    return {net: ",".join(sorted(pins)) for net, pins in rows.items()}


def _result_dict(result: MappingResult) -> dict:
    return {
        "solver": result.solver,
        "ok": result.ok,
        "assignments": [
            {
                "net_name": assignment.net_name,
                "pin_name": assignment.pin_name,
                "pin_index": assignment.pin_index,
                "score": assignment.score,
            }
            for assignment in result.assignments
        ],
        "unmapped": [req.net_name for req in result.unmapped],
        "errors": result.errors,
        "warnings": result.warnings,
        "objective_score": result.objective_score,
    }
