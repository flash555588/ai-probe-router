"""Signal-aware scoring for probe placement decisions.

Adjusts placement candidate scores based on the electrical role and
sub-role of each net, encoding hardware design best practices.
"""

from __future__ import annotations

import math

from ..models.board import Board
from ..models.net import NetRole, NetSubRole


def signal_score(
    x: float,
    y: float,
    role: NetRole,
    sub_roles: set[NetSubRole],
    board: Board,
) -> tuple[float, list[str]]:
    """Return (score_adjustment, warnings) for a probe candidate position.

    Positive values favor the position; negative values penalize it.
    """
    score = 0.0
    warnings: list[str] = []

    if NetSubRole.STRAPPING_PIN in sub_roles:
        score += _strapping_score(x, y, board, warnings)

    if NetSubRole.ADC_INPUT in sub_roles:
        score += _adc_score(x, y, board, warnings)

    if role == NetRole.POWER:
        score += _power_score(x, y, board)

    if NetSubRole.AUDIO_ANALOG in sub_roles:
        score += _audio_score(x, y, board, warnings)

    if NetSubRole.BATTERY in sub_roles:
        warnings.append("Battery net — verify probe does not bypass protection circuit")

    return score, warnings


def _strapping_score(
    x: float,
    y: float,
    board: Board,
    warnings: list[str],
) -> float:
    ic_footprints = [
        fp for fp in board.footprints
        if fp.ref.startswith("U") or fp.ref.startswith("IC")
    ]
    if not ic_footprints:
        return 0.0

    min_dist = min(
        math.hypot(x - fp.x, y - fp.y) for fp in ic_footprints
    )
    if min_dist < 3.0:
        warnings.append(
            f"Strapping pin probe {min_dist:.1f}mm from IC — "
            "added capacitance may affect boot behavior"
        )
        return -2.0
    if min_dist > 8.0:
        return 1.0
    return 0.0


def _adc_score(
    x: float,
    y: float,
    board: Board,
    warnings: list[str],
) -> float:
    clock_pads = []
    for fp in board.footprints:
        for pad in fp.pads:
            net = pad.net_name.upper() if pad.net_name else ""
            if any(kw in net for kw in ("CLK", "CLOCK", "XTAL", "OSC", "BCLK")):
                abs_x = fp.x + pad.x
                abs_y = fp.y + pad.y
                clock_pads.append((abs_x, abs_y))

    if not clock_pads:
        return 0.0

    min_dist = min(
        math.hypot(x - cx, y - cy) for cx, cy in clock_pads
    )
    if min_dist < 3.0:
        warnings.append(
            f"ADC probe {min_dist:.1f}mm from clock signal — noise coupling risk"
        )
        return -3.0
    if min_dist < 5.0:
        return -1.0
    return 0.5


def _power_score(x: float, y: float, board: Board) -> float:
    ic_footprints = [
        fp for fp in board.footprints
        if fp.ref.startswith("U") or fp.ref.startswith("IC")
    ]
    if not ic_footprints:
        return 0.0

    min_dist = min(
        math.hypot(x - fp.x, y - fp.y) for fp in ic_footprints
    )
    if min_dist < 5.0:
        return 1.0
    return 0.0


def _audio_score(
    x: float,
    y: float,
    board: Board,
    warnings: list[str],
) -> float:
    clock_pads = []
    for fp in board.footprints:
        for pad in fp.pads:
            net = pad.net_name.upper() if pad.net_name else ""
            if any(kw in net for kw in ("CLK", "CLOCK", "XTAL", "OSC")):
                abs_x = fp.x + pad.x
                abs_y = fp.y + pad.y
                clock_pads.append((abs_x, abs_y))

    if not clock_pads:
        return 0.0

    min_dist = min(
        math.hypot(x - cx, y - cy) for cx, cy in clock_pads
    )
    if min_dist < 3.0:
        warnings.append(
            f"Audio probe {min_dist:.1f}mm from clock — crosstalk risk"
        )
        return -2.0
    return 0.0
