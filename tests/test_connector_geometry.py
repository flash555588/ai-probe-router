from ai_probe_router.config import ProjectConfig
from ai_probe_router.engine import _run_phase2
from ai_probe_router.models.board import Board, EdgeSegment
from ai_probe_router.models.dev_board import DevBoardPin, DevelopmentBoard
from ai_probe_router.models.probe import ProbeConfig, ProbeRequirement, ProbeStyle


def test_phase2_connector_uses_dev_board_rows_and_pins_per_row():
    board = Board(
        edges=[
            EdgeSegment(0, 0, 20, 0),
            EdgeSegment(20, 0, 20, 20),
            EdgeSegment(20, 20, 0, 20),
            EdgeSegment(0, 20, 0, 0),
        ],
        raw=["kicad_pcb"],
    )
    dev_board = DevelopmentBoard(
        name="tiny_header",
        rows=1,
        pins_per_row=4,
        pins=[
            DevBoardPin(name="GND", capabilities=["GND"], is_ground=True),
            DevBoardPin(name="3V3", capabilities=["POWER_3V3"], is_power=True),
            DevBoardPin(name="PA0", capabilities=["GPIO"]),
            DevBoardPin(name="PA1", capabilities=["GPIO"]),
        ],
    )
    cfg = ProjectConfig(
        probe=ProbeConfig(style=ProbeStyle.CONNECTOR, side="top"),
        nets_to_expose=[ProbeRequirement(net_name="GND", role="ground")],
    )

    report = _run_phase2(cfg, board, None, dev_board)

    assert report.result.ok
    connector = next(fp for fp in board.footprints if fp.ref == "J1")
    assert len(connector.pads) == 4
    assert "PinHeader_1x4" in connector.lib_id

