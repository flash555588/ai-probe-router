"""Phase 2: development-board pin mapping and connector synthesis."""

from __future__ import annotations

from ..config import ProjectConfig
from ..eda_adapters.kicad.pcb_writer import (
    add_connector_footprint,
    add_keepout_zone,
)
from ..eda_adapters.kicad.sch_writer import add_connector_symbol
from ..models.board import Board, Schematic
from ..models.dev_board import DevelopmentBoard
from ..models.probe import ProbeStyle
from ..solvers.pin_mapper import solve_mapping
from ..verification.pin_report import PinMapReport


def run_phase2(
    cfg: ProjectConfig,
    board: Board | None,
    sch: Schematic | None,
    dev_board: DevelopmentBoard,
) -> PinMapReport:
    result = solve_mapping(cfg.nets_to_expose, dev_board)
    pin_report = PinMapReport(
        board_name=dev_board.name,
        result=result,
    )

    if cfg.probe.style != ProbeStyle.CONNECTOR:
        return pin_report

    if result.assignments:
        rows = dev_board.rows
        pins_per_row = dev_board.pins_per_row
        if sch is not None:
            add_connector_symbol(
                sch, result.assignments,
                ref="J1",
                x=80.0, y=50.0,
                rows=rows,
                pins_per_row=pins_per_row,
            )
        if board is not None:
            bounds = board.board_bounds()
            if bounds:
                # Place connector to the right of the board, aligned vertically
                conn_w = pins_per_row * dev_board.pitch_mm
                conn_h = rows * dev_board.pitch_mm
                margin = 5.0
                cx = bounds.max_x + margin
                cy = (bounds.min_y + bounds.max_y) / 2 - conn_h / 2
            else:
                conn_w = pins_per_row * dev_board.pitch_mm
                conn_h = rows * dev_board.pitch_mm
                cx, cy = 150.0, 100.0
            add_connector_footprint(
                board, result.assignments,
                ref="J1",
                x=cx, y=cy,
                rows=rows,
                pins_per_row=pins_per_row,
                pitch=dev_board.pitch_mm,
                side=cfg.probe.side,
            )
            # Keepout around connector
            add_keepout_zone(
                board, cx + conn_w / 2, cy + conn_h / 2,
                conn_w + 2.0, conn_h + 2.0,
            )

    return pin_report
