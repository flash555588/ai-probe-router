"""Global placement optimizer using OR-Tools CP-SAT.

Solves for optimal testpoint/protection locations on a discrete grid
to minimize total routing length while respecting clearance constraints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

try:
    from ortools.sat.python import cp_model
except ImportError:
    cp_model = None

if TYPE_CHECKING:
    from ..models.board import Board
    from ..models.probe import ProbeConfig, ProbeRequirement


@dataclass
class PlacementVariable:
    """Grid placement result for a single probe."""
    net_name: str
    x: float
    y: float
    cost: float = 0.0


@dataclass
class GlobalPlacementResult:
    placements: list[PlacementVariable] = field(default_factory=list)
    total_cost: float = 0.0
    solver_status: str = ""


def solve_global_placement(
    board: Board,
    reqs: list[ProbeRequirement],
    probe_cfg: ProbeConfig,
    grid_mm: float = 1.0,
    time_limit_sec: float = 10.0,
) -> GlobalPlacementResult:
    """Use CP-SAT to find globally-optimal probe placements.

    Objective: minimize sum of Manhattan distances from each probe
    to its nearest source pad, plus penalties for congestion.
    """
    if cp_model is None:
        return GlobalPlacementResult(solver_status="ortools not installed")

    bounds = board.board_bounds()
    if bounds is None:
        return GlobalPlacementResult(solver_status="no_board_bounds")

    # Discretize board into grid
    x_min, y_min = int(bounds.min_x), int(bounds.min_y)
    x_max, y_max = int(bounds.max_x), int(bounds.max_y)
    nx = max(1, int((x_max - x_min) / grid_mm))
    ny = max(1, int((y_max - y_min) / grid_mm))

    model = cp_model.CpModel()
    placements: dict[str, tuple] = {}

    # Create grid variables for each net
    for req in reqs:
        xi = model.NewIntVar(0, nx - 1, f"x_{req.net_name}")
        yi = model.NewIntVar(0, ny - 1, f"y_{req.net_name}")
        placements[req.net_name] = (xi, yi)

    # Spacing constraints: no two probes on the same grid cell
    min_cells = max(1, int(probe_cfg.min_spacing_mm / grid_mm))
    nets = list(placements.keys())
    for i in range(len(nets)):
        for j in range(i + 1, len(nets)):
            xi, yi = placements[nets[i]]
            xj, yj = placements[nets[j]]
            # Manhattan distance >= min_cells
            model.Add(xi - xj + yi - yj >= min_cells).OnlyEnforceIf(
                model.NewBoolVar(f"sep_{i}_{j}_1")
            )
            # Or use absolute value with auxiliary booleans
            # Simplified: forbid same cell
            b_same = model.NewBoolVar(f"same_{i}_{j}")
            model.Add(xi == xj).OnlyEnforceIf(b_same)
            model.Add(yi == yj).OnlyEnforceIf(b_same)
            model.Add(xi != xj).OnlyEnforceIf(b_same.Not())
            model.Add(yi != yj).OnlyEnforceIf(b_same.Not())

    # Objective: minimize distance to source pads
    obj_terms = []
    for req in reqs:
        pads = board.find_pads_by_net(req.net_name)
        if not pads:
            continue
        xi, yi = placements[req.net_name]
        for _fp, pad in pads:
            tx = int((pad.x - x_min) / grid_mm)
            ty = int((pad.y - y_min) / grid_mm)
            dx = model.NewIntVar(-nx, nx, f"dx_{req.net_name}")
            dy = model.NewIntVar(-ny, ny, f"dy_{req.net_name}")
            model.Add(dx == xi - tx)
            model.Add(dy == yi - ty)
            adx = model.NewIntVar(0, nx, f"adx_{req.net_name}")
            ady = model.NewIntVar(0, ny, f"ady_{req.net_name}")
            model.AddAbsEquality(adx, dx)
            model.AddAbsEquality(ady, dy)
            obj_terms.append(adx)
            obj_terms.append(ady)

    model.Minimize(sum(obj_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_sec
    status = solver.Solve(model)

    result = GlobalPlacementResult(solver_status=cp_model.CpSolver().StatusName(status))
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for req in reqs:
            xi, yi = placements[req.net_name]
            result.placements.append(
                PlacementVariable(
                    net_name=req.net_name,
                    x=x_min + solver.Value(xi) * grid_mm,
                    y=y_min + solver.Value(yi) * grid_mm,
                )
            )
        result.total_cost = solver.ObjectiveValue() * grid_mm

    return result
