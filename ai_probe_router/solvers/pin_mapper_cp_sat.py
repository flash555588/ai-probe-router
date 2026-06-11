"""OR-Tools CP-SAT based pin mapper.

Replaces the deterministic greedy solver with a global combinatorial
optimization model that is insensitive to input ordering.
"""

from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

from ..models.dev_board import DevBoardPin, DevelopmentBoard
from ..models.probe import ProbeRequirement
from .pin_mapper import (
    MappingResult,
    PinAssignment,
    _build_pair_map,
    _is_adjacent,
    _role_to_capabilities,
    _score_match,
)


@dataclass
class _PinScore:
    pin: DevBoardPin
    index: int
    score: int


def solve_mapping_cp_sat(
    requirements: list[ProbeRequirement],
    board: DevelopmentBoard,
    time_limit_sec: float = 5.0,
) -> MappingResult:
    """Solve pin mapping with OR-Tools CP-SAT.

    Falls back to an empty MappingResult if no feasible solution is found
    within the time limit.
    """
    pair_map = _build_pair_map(requirements)
    processed: set[str] = set()

    # Split requirements into singles and pairs
    single_reqs: list[ProbeRequirement] = []
    pair_reqs: list[tuple[ProbeRequirement, ProbeRequirement]] = []

    for req in requirements:
        if req.net_name in processed:
            continue
        pair = pair_map.get(req.net_name)
        if pair is not None and pair.net_name not in processed:
            pair_reqs.append((req, pair))
            processed.add(req.net_name)
            processed.add(pair.net_name)
        else:
            single_reqs.append(req)
            processed.add(req.net_name)

    model = cp_model.CpModel()

    # --- Precompute eligible pins and scores ---
    def _eligible_pins(req: ProbeRequirement) -> list[_PinScore]:
        needed = _role_to_capabilities(req.role, req.net_name, req.pair_net_name)
        results: list[_PinScore] = []
        for idx, pin in enumerate(board.pins):
            if req.current_ma > 0 and pin.current_rating_ma < req.current_ma:
                continue
            pin_caps = set(pin.capabilities) | set(pin.alternate_functions)
            if not (needed & pin_caps):
                continue
            score = int(_score_match(pin, needed & pin_caps, needed, req))
            results.append(_PinScore(pin=pin, index=idx, score=score))
        return results

    # Singles
    single_eligible: dict[int, list[_PinScore]] = {}
    single_idx_map: dict[int, ProbeRequirement] = {}
    for i, req in enumerate(single_reqs):
        single_eligible[i] = _eligible_pins(req)
        single_idx_map[i] = req

    # Pairs
    pair_eligible: dict[int, tuple[list[_PinScore], list[_PinScore]]] = {}
    pair_idx_map: dict[int, tuple[ProbeRequirement, ProbeRequirement]] = {}
    # slot_idx -> (pin_a_idx, pin_b_idx, score)
    pair_adjacent_slots: dict[int, list[tuple[int, int, int]]] = {}
    for i, (req_a, req_b) in enumerate(pair_reqs):
        pair_idx_map[i] = (req_a, req_b)
        eligible_a = _eligible_pins(req_a)
        eligible_b = _eligible_pins(req_b)
        pair_eligible[i] = (eligible_a, eligible_b)

        # Enumerate all adjacent feasible pin pairs
        slots: list[tuple[int, int, int]] = []
        for ps_a in eligible_a:
            for ps_b in eligible_b:
                if ps_a.index == ps_b.index:
                    continue
                if _is_adjacent(ps_a.index, ps_b.index, board.pins_per_row):
                    slot_score = ps_a.score + ps_b.score
                    slots.append((ps_a.index, ps_b.index, slot_score))
        pair_adjacent_slots[i] = slots

    # --- Variables ---
    # Single assignments
    single_vars: dict[tuple[int, int], cp_model.IntVar] = {}
    for si, eligible in single_eligible.items():
        for ps in eligible:
            single_vars[(si, ps.index)] = model.NewBoolVar(f"single_s{si}_p{ps.index}")

    # Pair slot selections
    pair_slot_vars: dict[tuple[int, int], cp_model.IntVar] = {}
    for pi, slots in pair_adjacent_slots.items():
        for slot_i, _ in enumerate(slots):
            pair_slot_vars[(pi, slot_i)] = model.NewBoolVar(f"pair_p{pi}_slot{slot_i}")

    # --- Constraints ---
    # 1. Each single req gets exactly count pins
    for si, req in enumerate(single_reqs):
        count = max(req.duplicate_probe_count, 1)
        eligible_pins = [ps.index for ps in single_eligible[si]]
        if not eligible_pins:
            # No eligible pins for this req - model infeasible
            return MappingResult(errors=[f"No eligible pins for {req.net_name}"])
        model.Add(
            sum(single_vars[(si, p)] for p in eligible_pins) == count
        )

    # 2. Each pair gets exactly one slot (one adjacent pin pair)
    for pi, slots in pair_adjacent_slots.items():
        if not slots:
            req_a, req_b = pair_idx_map[pi]
            return MappingResult(
                errors=[f"No adjacent pin pair for differential pair "
                        f"{req_a.net_name}/{req_b.net_name}"]
            )
        model.Add(sum(pair_slot_vars[(pi, s)] for s in range(len(slots))) == 1)

    # 3. Each pin used at most once (singles + pairs)
    for pin_idx in range(len(board.pins)):
        terms: list[cp_model.IntVar] = []
        # Singles using this pin
        for si, eligible in single_eligible.items():
            if any(ps.index == pin_idx for ps in eligible):
                terms.append(single_vars[(si, pin_idx)])
        # Pairs using this pin
        for pi, slots in pair_adjacent_slots.items():
            for slot_i, (p_a, p_b, _) in enumerate(slots):
                if p_a == pin_idx or p_b == pin_idx:
                    terms.append(pair_slot_vars[(pi, slot_i)])
        if terms:
            model.Add(sum(terms) <= 1)

    # 4. Link pair slots to implied pin occupancy
    for pi, slots in pair_adjacent_slots.items():
        req_a, req_b = pair_idx_map[pi]
        # For each eligible pin of req_a, ensure it's used iff a slot selecting it is chosen
        for ps in pair_eligible[pi][0]:
            covering_slots = [
                slot_i for slot_i, (p_a, _, _) in enumerate(slots) if p_a == ps.index
            ]
            if covering_slots:
                # The pin can be used by at most one slot, but since slots are
                # mutually exclusive per pair, the sum is either 0 or 1.
                # We don't need an explicit link variable for occupancy because
                # constraint #3 already limits pin usage.
                pass

    # --- Objective ---
    obj_terms: list[cp_model.IntVar] = []
    obj_coeffs: list[int] = []

    for si, eligible in single_eligible.items():
        for ps in eligible:
            obj_terms.append(single_vars[(si, ps.index)])
            obj_coeffs.append(ps.score)

    for pi, slots in pair_adjacent_slots.items():
        for slot_i, (_, _, score) in enumerate(slots):
            obj_terms.append(pair_slot_vars[(pi, slot_i)])
            obj_coeffs.append(score)

    model.Maximize(sum(c * v for c, v in zip(obj_coeffs, obj_terms)))

    # --- Solve ---
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_sec
    solver.parameters.num_search_workers = 4
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return MappingResult(
            errors=["CP-SAT could not find a feasible pin assignment"]
        )

    # --- Extract result ---
    result = MappingResult()

    for si, req in enumerate(single_reqs):
        count = max(req.duplicate_probe_count, 1)
        assigned = 0
        for ps in single_eligible[si]:
            if solver.Value(single_vars[(si, ps.index)]) == 1:
                result.assignments.append(PinAssignment(
                    net_name=req.net_name,
                    pin_name=ps.pin.name,
                    pin_index=ps.index,
                    score=float(ps.score),
                ))
                assigned += 1
        if assigned < count and req.required:
            result.errors.append(
                f"CP-SAT under-assigned required net {req.net_name}"
            )

    for pi, (req_a, req_b) in enumerate(pair_reqs):
        slots = pair_adjacent_slots[pi]
        for slot_i, (p_a, p_b, score) in enumerate(slots):
            if solver.Value(pair_slot_vars[(pi, slot_i)]) == 1:
                pin_a = board.pins[p_a]
                pin_b = board.pins[p_b]
                result.assignments.append(PinAssignment(
                    net_name=req_a.net_name,
                    pin_name=pin_a.name,
                    pin_index=p_a,
                    score=float(score) / 2,
                ))
                result.assignments.append(PinAssignment(
                    net_name=req_b.net_name,
                    pin_name=pin_b.name,
                    pin_index=p_b,
                    score=float(score) / 2,
                ))
                break

    return result
