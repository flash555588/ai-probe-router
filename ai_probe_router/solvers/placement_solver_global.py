"""Global probe placement solver using OR-Tools CP-SAT.

Replaces the per-net greedy placement with a joint optimization that
selects positions for all nets simultaneously, eliminating ordering bias.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

try:
    from ortools.sat.python import cp_model
except ImportError:  # optional dependency (.[solver] extra)
    cp_model = None

from ..models.board import Board
from ..models.constraints import Constraints
from ..models.net import NetRole, NetSubRole
from ..models.probe import ProbeConfig, ProbeRequirement
from .constraint_checker import check_placement
from .placement_solver import _generate_candidates
from .routing_cost import estimate_routing_cost
from .signal_aware_scoring import signal_score


@dataclass
class PlacementTask:
    """A single probe placement requirement."""

    req: ProbeRequirement
    index: int  # duplicate index within the net
    role: NetRole
    sub_roles: set[NetSubRole]


@dataclass
class _ScoredCandidate:
    x: float
    y: float
    score: float
    warnings: list[str] = field(default_factory=list)


def solve_placement_global(
    board: Board,
    tasks: list[PlacementTask],
    probe_cfg: ProbeConfig,
    constraints: Constraints,
    *,
    max_candidates_per_task: int = 30,
    time_limit_sec: float = 5.0,
) -> dict[tuple[str, int], tuple[float, float] | None]:
    """Solve placement globally with CP-SAT.

    Returns a mapping ``{(net_name, duplicate_index): (x, y) | None}``.
    A *None* value means no feasible placement was found for that task.
    """
    if cp_model is None or not tasks:
        return {}

    # --- 1. Generate candidates for every task independently ---
    task_candidates: list[list[_ScoredCandidate]] = []
    for task in tasks:
        candidates = _generate_and_score_candidates(
            board, task, probe_cfg, constraints,
        )
        candidates.sort(key=lambda c: c.score, reverse=True)
        task_candidates.append(candidates[:max_candidates_per_task])

    # --- 2. Build CP-SAT model ---
    model = cp_model.CpModel()

    # Variables: sel[t][c] == 1 iff task t selects candidate c
    sel: list[list[cp_model.IntVar]] = []
    for t_idx, candidates in enumerate(task_candidates):
        vars_t = [
            model.NewBoolVar(f"sel_t{t_idx}_c{c_idx}")
            for c_idx in range(len(candidates))
        ]
        sel.append(vars_t)

    # Constraint: each task selects exactly one candidate
    for t_idx, vars_t in enumerate(sel):
        if not vars_t:
            return {
                (tasks[t_idx].req.net_name, tasks[t_idx].index): None
                for t_idx in range(len(tasks))
            }
        model.AddExactlyOne(vars_t)

    min_spacing = probe_cfg.min_spacing_mm

    obj_terms: list[cp_model.IntVar] = []
    obj_coeffs: list[int] = []

    # Pair-wise constraints and bonuses
    for t1 in range(len(tasks)):
        cands1 = task_candidates[t1]
        for t2 in range(t1 + 1, len(tasks)):
            cands2 = task_candidates[t2]
            is_pair = (
                tasks[t1].req.pair_net_name == tasks[t2].req.net_name
                and tasks[t2].req.pair_net_name == tasks[t1].req.net_name
            )
            for c1_idx, c1 in enumerate(cands1):
                for c2_idx, c2 in enumerate(cands2):
                    dist = math.hypot(c1.x - c2.x, c1.y - c2.y)
                    # Use a tight tolerance to avoid floating-point edge cases
                    # where snapped grid points are *just* under the threshold.
                    if dist <= min_spacing + 1e-3:
                        model.Add(sel[t1][c1_idx] + sel[t2][c2_idx] <= 1)
                    elif is_pair and dist <= min_spacing * 2:
                        bonus = int(round(max(0.0, 50.0 - dist * 10.0)))
                        if bonus > 0:
                            and_var = model.NewBoolVar(
                                f"pair_t{t1}c{c1_idx}_t{t2}c{c2_idx}"
                            )
                            model.Add(
                                sel[t1][c1_idx] + sel[t2][c2_idx] >= 2
                            ).OnlyEnforceIf(and_var)
                            model.Add(
                                sel[t1][c1_idx] + sel[t2][c2_idx] <= 1
                            ).OnlyEnforceIf(and_var.Not())
                            obj_terms.append(and_var)
                            obj_coeffs.append(bonus)

    # Objective: maximise candidate scores
    for t_idx, candidates in enumerate(task_candidates):
        for c_idx, cand in enumerate(candidates):
            obj_terms.append(sel[t_idx][c_idx])
            obj_coeffs.append(int(round(cand.score)))

    model.Maximize(sum(c * v for c, v in zip(obj_coeffs, obj_terms)))

    # --- 3. Solve ---
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_sec
    solver.parameters.num_search_workers = 4
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            (task.req.net_name, task.index): None
            for task in tasks
        }

    # --- 4. Extract results ---
    result: dict[tuple[str, int], tuple[float, float] | None] = {}
    for t_idx, task in enumerate(tasks):
        chosen = None
        for c_idx, _ in enumerate(task_candidates[t_idx]):
            if solver.Value(sel[t_idx][c_idx]) == 1:
                chosen = task_candidates[t_idx][c_idx]
                break
        if chosen is not None:
            result[(task.req.net_name, task.index)] = (chosen.x, chosen.y)
        else:
            result[(task.req.net_name, task.index)] = None

    return result


def _generate_and_score_candidates(
    board: Board,
    task: PlacementTask,
    probe_cfg: ProbeConfig,
    constraints: Constraints,
) -> list[_ScoredCandidate]:
    """Generate and score candidates for a single task, ignoring existing probes."""
    req = task.req
    pads = board.find_pads_by_net(req.net_name)
    target_positions = [(p.x, p.y) for _, p in pads]
    if not target_positions:
        return []

    # Generate candidates without pairing info
    raw_cands = _generate_candidates(
        board, target_positions, probe_cfg, task.index,
        paired_mate_position=None,
    )

    scored: list[_ScoredCandidate] = []
    for c in raw_cands:
        # Independent checks only (ignore existing_probes for now)
        check = check_placement(
            c.x, c.y, board, constraints, probe_cfg,
            existing_probes=None, net_name=req.net_name,
        )
        if not check.ok:
            continue

        score = c.score
        sig_adj, sig_warns = signal_score(
            c.x, c.y, task.role, task.sub_roles, board,
        )
        score += sig_adj
        cost = estimate_routing_cost(c.x, c.y, target_positions, board)
        score -= cost.total

        scored.append(_ScoredCandidate(
            x=c.x, y=c.y, score=score, warnings=list(sig_warns),
        ))

    return scored
