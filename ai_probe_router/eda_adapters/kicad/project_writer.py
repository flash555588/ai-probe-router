"""Write a ``.kicad_pro`` project file carrying the configured design rules.

Without a project file next to the board, ``kicad-cli pcb drc`` falls back
to KiCad's factory design rules (e.g. min track width 0.2 mm), so native
validation would judge the output against rules the user never configured.
Writing the project file makes the config the single source of truth for
both generation and native DRC.
"""

from __future__ import annotations

import json
from pathlib import Path

from ...models.constraints import Constraints


def design_rules_from_constraints(constraints: Constraints) -> dict[str, float]:
    """Map APR constraints onto KiCad board design rules."""
    mfg = constraints.manufacturing
    routing = constraints.routing
    return {
        "min_clearance": max(mfg.min_clearance_mm, routing.min_clearance_mm),
        "min_track_width": mfg.min_trace_width_mm,
        "min_through_hole_diameter": mfg.min_drill_mm,
    }


def write_project_file(
    out_pcb_path: Path,
    constraints: Constraints,
    *,
    source_project: Path | None = None,
) -> Path:
    """Write ``<board>.kicad_pro`` next to the output PCB.

    If ``source_project`` exists its contents are preserved and only the
    design rules are overridden; otherwise a minimal project is created.
    """
    pro_path = out_pcb_path.with_suffix(".kicad_pro")

    project: dict = {}
    if source_project is not None and source_project.is_file():
        try:
            project = json.loads(source_project.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            project = {}

    rules = (
        project.setdefault("board", {})
        .setdefault("design_settings", {})
        .setdefault("rules", {})
    )
    rules.update(design_rules_from_constraints(constraints))
    project.setdefault("meta", {"filename": pro_path.name, "version": 3})
    project["meta"]["filename"] = pro_path.name

    pro_path.write_text(
        json.dumps(project, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return pro_path
