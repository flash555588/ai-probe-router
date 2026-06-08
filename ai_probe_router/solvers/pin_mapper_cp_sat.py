"""Optional OR-Tools CP-SAT pin mapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models.dev_board import DevBoardPin, DevelopmentBoard
from ..models.probe import ProbeRequirement
from .pin_mapper import (
    MappingResult,
    PinAssignment,
    _find_candidates,
    _is_adjacent,
)


@dataclass(frozen=True)
class CpSatPinMapperWeights:
    preferred_pin: int = 100
    capability_match: int = 80
    current_margin: int = 30
    preserve_spare_pins: int = 5
    duplicate_probe_grouping: int = 20
    differential_pair_adjacency: int = 50
    route_length: int = 1


def ortools_available() -> bool:
    try:
        from ortools.sat.python import cp_model  # noqa: F401
    except ImportError:
        return False
    return True


def map_pins_cp_sat(
    requirements: list[ProbeRequirement],
    development_board: DevelopmentBoard,
    constraints: Any = None,
    weights: Any = None,
) -> MappingResult:
    del constraints
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return MappingResult(
            errors=["CP_SAT_REQUIRED_BUT_ORTOOLS_MISSING"],
            solver="cp_sat",
        )

    weight = _coerce_weights(weights)
    units = _assignment_units(requirements)
    candidates_by_unit: dict[int, list[_CpCandidate]] = {}
    result = MappingResult(solver="cp_sat")

    for unit_index, unit in enumerate(units):
        candidates = _unit_candidates(development_board, unit, set(), unit.duplicate_index)
        if unit.preferred_devboard_pins:
            preferred = [
                candidate for candidate in candidates
                if candidate.pin.name in unit.preferred_devboard_pins
            ]
            if preferred:
                candidates = preferred
        if not candidates:
            if unit.required:
                result.errors.append(
                    f"CP_SAT_NO_FEASIBLE_MAPPING: no candidate pin for {unit.net_name}",
                )
            result.unmapped.append(unit)
        candidates_by_unit[unit_index] = candidates

    if result.errors:
        return result

    model = cp_model.CpModel()
    variables: dict[tuple[int, int], Any] = {}
    pin_to_variables: dict[int, list[Any]] = {}

    for unit_index, candidates in candidates_by_unit.items():
        unit_vars = []
        for candidate_index, candidate in enumerate(candidates):
            var = model.NewBoolVar(f"u{unit_index}_p{candidate.pin_index}")
            variables[(unit_index, candidate_index)] = var
            unit_vars.append(var)
            pin_to_variables.setdefault(candidate.pin_index, []).append(var)
        model.AddExactlyOne(unit_vars)

    for pin_vars in pin_to_variables.values():
        model.AddAtMostOne(pin_vars)

    _add_differential_pair_constraints(
        model,
        variables,
        units,
        candidates_by_unit,
        development_board,
    )

    model.Maximize(
        sum(
            variables[(unit_index, candidate_index)]
            * _candidate_score(unit, candidate, weight)
            for unit_index, candidates in candidates_by_unit.items()
            for candidate_index, candidate in enumerate(candidates)
        )
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5
    solver.parameters.num_search_workers = 1
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return MappingResult(
            errors=["CP_SAT_NO_FEASIBLE_MAPPING"],
            unmapped=list(requirements),
            solver="cp_sat",
        )

    assignments: list[PinAssignment] = []
    for unit_index, candidates in candidates_by_unit.items():
        unit = units[unit_index]
        for candidate_index, candidate in enumerate(candidates):
            if solver.BooleanValue(variables[(unit_index, candidate_index)]):
                assignments.append(
                    PinAssignment(
                        net_name=unit.net_name,
                        pin_name=candidate.pin.name,
                        pin_index=candidate.pin_index,
                        score=float(_candidate_score(unit, candidate, weight)),
                    )
                )
                break

    result.assignments = assignments
    result.objective_score = float(solver.ObjectiveValue())
    return result


@dataclass
class _CpCandidate:
    pin: DevBoardPin
    pin_index: int
    capability_matches: int
    current_margin_ma: float


@dataclass
class _AssignmentUnit(ProbeRequirement):
    duplicate_index: int = 0


def _assignment_units(requirements: list[ProbeRequirement]) -> list[_AssignmentUnit]:
    units: list[_AssignmentUnit] = []
    for req in requirements:
        count = max(req.duplicate_probe_count, 1)
        for duplicate_index in range(count):
            units.append(
                _AssignmentUnit(
                    net_name=req.net_name,
                    role=req.role,
                    required=req.required,
                    preferred_devboard_pins=req.preferred_devboard_pins,
                    duplicate_probe_count=req.duplicate_probe_count,
                    current_ma=req.current_ma,
                    pair_net_name=req.pair_net_name,
                    duplicate_index=duplicate_index,
                )
            )
    return units


def _unit_candidates(
    board: DevelopmentBoard,
    unit: _AssignmentUnit,
    used_pins: set[int],
    duplicate_index: int,
) -> list[_CpCandidate]:
    candidates = _find_candidates(board, _needed_caps(unit), unit, used_pins)
    if duplicate_index > 0 and unit.role.lower() not in {"ground", "gnd"}:
        return []
    return [
        _CpCandidate(
            pin=candidate.pin,
            pin_index=candidate.index,
            capability_matches=_capability_matches(candidate.pin, unit),
            current_margin_ma=max(candidate.pin.current_rating_ma - unit.current_ma, 0.0),
        )
        for candidate in candidates
    ]


def _needed_caps(unit: ProbeRequirement) -> set[str]:
    from .pin_mapper import _role_to_capabilities

    return _role_to_capabilities(unit.role, unit.net_name, unit.pair_net_name)


def _capability_matches(pin: DevBoardPin, unit: ProbeRequirement) -> int:
    pin_caps = set(pin.capabilities) | set(pin.alternate_functions)
    return len(pin_caps & _needed_caps(unit))


def _candidate_score(
    unit: _AssignmentUnit,
    candidate: _CpCandidate,
    weight: CpSatPinMapperWeights,
) -> int:
    score = candidate.capability_matches * weight.capability_match
    if candidate.pin.name in unit.preferred_devboard_pins:
        score += weight.preferred_pin
    if unit.role.lower() in {"ground", "gnd"} and candidate.pin.is_ground:
        score += weight.duplicate_probe_grouping
    if unit.role.lower() == "power" and candidate.pin.is_power:
        score += weight.current_margin
    score += int(candidate.current_margin_ma / 100) * weight.current_margin
    score -= len(candidate.pin.alternate_functions) * weight.preserve_spare_pins
    score -= candidate.pin_index * weight.route_length
    return score


def _add_differential_pair_constraints(
    model,
    variables: dict[tuple[int, int], Any],
    units: list[_AssignmentUnit],
    candidates_by_unit: dict[int, list[_CpCandidate]],
    board: DevelopmentBoard,
) -> None:
    by_net = {unit.net_name: index for index, unit in enumerate(units) if unit.duplicate_index == 0}
    for unit_index, unit in enumerate(units):
        if unit.duplicate_index != 0 or not unit.pair_net_name:
            continue
        pair_index = by_net.get(unit.pair_net_name)
        if pair_index is None or pair_index <= unit_index:
            continue
        for candidate_index, candidate in enumerate(candidates_by_unit[unit_index]):
            for pair_candidate_index, pair_candidate in enumerate(candidates_by_unit[pair_index]):
                if not _is_adjacent(
                    candidate.pin_index,
                    pair_candidate.pin_index,
                    board.pins_per_row,
                ):
                    model.Add(
                        variables[(unit_index, candidate_index)]
                        + variables[(pair_index, pair_candidate_index)]
                        <= 1
                    )


def _coerce_weights(weights: Any) -> CpSatPinMapperWeights:
    if weights is None:
        return CpSatPinMapperWeights()
    return CpSatPinMapperWeights(
        preferred_pin=int(getattr(weights, "preferred_pin", 100)),
        capability_match=int(getattr(weights, "capability_match", 80)),
        current_margin=int(getattr(weights, "current_margin", 30)),
        preserve_spare_pins=int(getattr(weights, "preserve_spare_pins", 5)),
        duplicate_probe_grouping=int(getattr(weights, "duplicate_probe_grouping", 20)),
        differential_pair_adjacency=int(
            getattr(weights, "differential_pair_adjacency", 50),
        ),
        route_length=int(getattr(weights, "route_length", 1)),
    )
