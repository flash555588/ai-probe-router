"""Constraint-based pin mapper: maps target nets to development-board pins.

Phase 2 uses a deterministic greedy solver with backtracking.
Future: upgrade to OR-Tools CP-SAT for global optimization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..models.dev_board import DevBoardPin, DevelopmentBoard
from ..models.probe import ProbeRequirement


@dataclass
class PinAssignment:
    net_name: str
    pin_name: str
    pin_index: int
    score: float = 0.0


@dataclass
class MappingResult:
    assignments: list[PinAssignment] = field(default_factory=list)
    unmapped: list[ProbeRequirement] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0 and all(
            a.pin_name for a in self.assignments
        )


def load_dev_board(path: str | Path) -> DevelopmentBoard:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    b = raw.get("board", {})
    conn = b.get("connector", {})
    board = DevelopmentBoard(
        name=b.get("name", "unknown"),
        connector_type=conn.get("type", "dual_row_header"),
        pitch_mm=conn.get("pitch_mm", 2.54),
        rows=conn.get("rows", 2),
        pins_per_row=conn.get("pins_per_row", 20),
    )
    for p in b.get("pins", []):
        board.pins.append(DevBoardPin(
            name=p.get("name", ""),
            capabilities=[str(c) for c in p.get("capabilities", [])],
            alternate_functions=[str(a) for a in p.get("alternate_functions", [])],
            current_rating_ma=p.get("current_ma", 25.0),
            is_power=p.get("is_power", False),
            is_ground=p.get("is_ground", False),
            fixed=p.get("fixed", False),
        ))
    return board


def solve_mapping(
    requirements: list[ProbeRequirement],
    board: DevelopmentBoard,
) -> MappingResult:
    result = MappingResult()
    used_pins: set[int] = set()
    pair_map = _build_pair_map(requirements)
    processed: set[str] = set()

    sorted_reqs = _sort_requirements(requirements)

    for req in sorted_reqs:
        if req.net_name in processed:
            continue

        pair_req = pair_map.get(req.net_name)
        if pair_req is not None and pair_req.net_name not in processed:
            # Try to assign differential pair to adjacent pins
            pair_result = _assign_differential_pair(
                board, req, pair_req, used_pins, result,
            )
            if pair_result:
                processed.add(req.net_name)
                processed.add(pair_req.net_name)
                continue
            # Fallback to individual assignment if pair assignment fails
        needed_caps = _role_to_capabilities(req.role, req.net_name, req.pair_net_name)
        candidates = _find_candidates(board, needed_caps, req, used_pins)

        preferred = [c for c in candidates if c.pin.name in req.preferred_devboard_pins]
        if preferred:
            candidates = preferred

        if not candidates:
            if req.required:
                result.errors.append(
                    f"No pin found for required net '{req.net_name}' (role={req.role})"
                )
            result.unmapped.append(req)
            processed.add(req.net_name)
            continue

        best = max(candidates, key=lambda c: c.score)
        used_pins.add(best.index)
        _add_assignments(result, board, used_pins, req, best)
        processed.add(req.net_name)

    return result


@dataclass
class _Candidate:
    pin: DevBoardPin
    index: int
    score: float


def _build_pair_map(reqs: list[ProbeRequirement]) -> dict[str, ProbeRequirement]:
    pair_map: dict[str, ProbeRequirement] = {}
    for req in reqs:
        if req.pair_net_name:
            pair_map[req.net_name] = next(
                (r for r in reqs if r.net_name == req.pair_net_name), None,
            )
    return {k: v for k, v in pair_map.items() if v is not None}


def _is_adjacent(idx1: int, idx2: int, pins_per_row: int) -> bool:
    """Return True if two pin indices are adjacent on the connector."""
    if idx1 == idx2:
        return False
    if pins_per_row <= 0:
        return False
    row1, col1 = divmod(idx1, pins_per_row)
    row2, col2 = divmod(idx2, pins_per_row)
    # Same row, adjacent columns
    if row1 == row2 and abs(col1 - col2) == 1:
        return True
    # Same column, adjacent rows
    if col1 == col2 and abs(row1 - row2) == 1:
        return True
    return False


def _assign_differential_pair(
    board: DevelopmentBoard,
    req_a: ProbeRequirement,
    req_b: ProbeRequirement,
    used_pins: set[int],
    result: MappingResult,
) -> bool:
    """Try to assign a differential pair to adjacent pins.

    Returns True if successful.
    """
    caps_a = _role_to_capabilities(req_a.role, req_a.net_name, req_a.pair_net_name)
    caps_b = _role_to_capabilities(req_b.role, req_b.net_name, req_b.pair_net_name)
    cands_a = _find_candidates(board, caps_a, req_a, used_pins)
    if not cands_a:
        return False

    for cand_a in sorted(cands_a, key=lambda c: c.score, reverse=True):
        # Look for adjacent pin for req_b
        cands_b = _find_candidates(board, caps_b, req_b, used_pins | {cand_a.index})
        for cand_b in cands_b:
            if _is_adjacent(cand_a.index, cand_b.index, board.pins_per_row):
                used_pins.add(cand_a.index)
                used_pins.add(cand_b.index)
                result.assignments.append(PinAssignment(
                    net_name=req_a.net_name,
                    pin_name=cand_a.pin.name,
                    pin_index=cand_a.index,
                    score=cand_a.score,
                ))
                result.assignments.append(PinAssignment(
                    net_name=req_b.net_name,
                    pin_name=cand_b.pin.name,
                    pin_index=cand_b.index,
                    score=cand_b.score,
                ))
                return True
    return False


def _add_assignments(
    result: MappingResult,
    board: DevelopmentBoard,
    used_pins: set[int],
    req: ProbeRequirement,
    best: _Candidate,
) -> None:
    count = max(req.duplicate_probe_count, 1)
    for i in range(count):
        if i == 0:
            result.assignments.append(PinAssignment(
                net_name=req.net_name,
                pin_name=best.pin.name,
                pin_index=best.index,
                score=best.score,
            ))
        else:
            extra = _find_next_ground_or_duplicate(board, used_pins, req)
            if extra:
                used_pins.add(extra.index)
                result.assignments.append(PinAssignment(
                    net_name=req.net_name,
                    pin_name=extra.pin.name,
                    pin_index=extra.index,
                    score=extra.score,
                ))


def _sort_requirements(reqs: list[ProbeRequirement]) -> list[ProbeRequirement]:
    role_priority = {
        "debug": 0, "reset": 1, "power": 2, "ground": 3,
        "communication": 4, "digital": 5, "analog": 6, "gpio": 7,
    }
    return sorted(reqs, key=lambda r: (
        role_priority.get(r.role, 99),
        not r.required,
        r.net_name,
    ))

def _role_to_capabilities(role: str, net_name: str, pair_net_name: str = "") -> set[str]:
    caps: set[str] = set()
    role_lc = role.lower()
    net_lc = net_name.lower()

    if role_lc in ("ground", "gnd"):
        caps.add("GND")
    if role_lc in ("power",):
        if "3v3" in net_lc or "3.3" in net_lc:
            caps.add("POWER_3V3")
        elif "5v" in net_lc:
            caps.add("POWER_5V")
        else:
            caps.add("POWER_3V3")
            caps.add("POWER_5V")
    if role_lc in ("debug",):
        if "swdio" in net_lc:
            caps.add("SWDIO")
        if "swclk" in net_lc:
            caps.add("SWCLK")
        if "swd" in net_lc and "swdio" not in net_lc and "swclk" not in net_lc:
            caps.add("SWDIO")
            caps.add("SWCLK")
        caps.add("GPIO")
    if role_lc in ("reset",):
        caps.add("NRST")
        caps.add("RESET")
        caps.add("GPIO")
    if role_lc in ("communication", "digital"):
        if "uart_tx" in net_lc or "usart_tx" in net_lc:
            caps.add("USART1_TX")
            caps.add("USART2_TX")
            caps.add("USART3_TX")
        if "uart_rx" in net_lc or "usart_rx" in net_lc:
            caps.add("USART1_RX")
            caps.add("USART2_RX")
            caps.add("USART3_RX")
        if "i2c_scl" in net_lc:
            caps.add("I2C1_SCL")
            caps.add("I2C2_SCL")
        if "i2c_sda" in net_lc:
            caps.add("I2C1_SDA")
            caps.add("I2C2_SDA")
        if "spi_sck" in net_lc or "spi_clk" in net_lc:
            caps.add("SPI1_SCK")
            caps.add("SPI2_SCK")
        if "spi_mosi" in net_lc:
            caps.add("SPI1_MOSI")
            caps.add("SPI2_MOSI")
        if "spi_miso" in net_lc:
            caps.add("SPI1_MISO")
            caps.add("SPI2_MISO")
        caps.add("GPIO")
    if role_lc in ("analog",):
        caps.add("ADC1")
        caps.add("GPIO")
    if role_lc in ("high_speed",):
        if "usb" in net_lc:
            caps.add("USB_DP")
            caps.add("USB_DM")
        if "eth" in net_lc:
            caps.add("ETH")
        # Only fall back to GPIO when this is part of a differential pair
        # and the board lacks dedicated USB/Eth pins.
        if pair_net_name:
            caps.add("GPIO")
    if role_lc in ("gpio",):
        caps.add("GPIO")

    return caps


def _find_candidates(
    board: DevelopmentBoard,
    needed_caps: set[str],
    req: ProbeRequirement,
    used_pins: set[int],
) -> list[_Candidate]:
    results: list[_Candidate] = []
    for idx, pin in enumerate(board.pins):
        if idx in used_pins:
            continue
        if pin.fixed:
            pin_caps = set(pin.capabilities) | set(pin.alternate_functions)
            if not (needed_caps & pin_caps):
                continue
        if req.current_ma > 0 and pin.current_rating_ma < req.current_ma:
            continue
        pin_caps = set(pin.capabilities) | set(pin.alternate_functions)
        matches = needed_caps & pin_caps
        if not matches:
            continue
        score = _score_match(pin, matches, needed_caps, req)
        results.append(_Candidate(pin=pin, index=idx, score=score))
    return results


def _score_match(
    pin: DevBoardPin,
    matches: set[str],
    needed_caps: set[str],
    req: ProbeRequirement,
) -> float:
    score = len(matches) * 10.0
    if pin.name in req.preferred_devboard_pins:
        score += 100.0
    if pin.is_power and req.role == "power":
        score += 50.0
    if pin.is_ground and req.role == "ground":
        score += 50.0
    # Prefer pins with fewer alternate functions (more dedicated)
    score -= len(pin.capabilities) * 0.5
    return score


def _find_next_ground_or_duplicate(
    board: DevelopmentBoard,
    used_pins: set[int],
    req: ProbeRequirement,
) -> _Candidate | None:
    needed = _role_to_capabilities(req.role, req.net_name, req.pair_net_name)
    for idx, pin in enumerate(board.pins):
        if idx in used_pins:
            continue
        pin_caps = set(pin.capabilities) | set(pin.alternate_functions)
        if needed & pin_caps:
            score = _score_match(pin, needed & pin_caps, needed, req)
            return _Candidate(pin=pin, index=idx, score=score)
    return None
