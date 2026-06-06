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

    sorted_reqs = _sort_requirements(requirements)

    for req in sorted_reqs:
        needed_caps = _role_to_capabilities(req.role, req.net_name)
        candidates = _find_candidates(board, needed_caps, req, used_pins)

        # Prefer user-specified pins first
        preferred = [c for c in candidates if c.pin.name in req.preferred_devboard_pins]
        if preferred:
            candidates = preferred

        if not candidates:
            if req.required:
                result.errors.append(
                    f"No pin found for required net '{req.net_name}' (role={req.role})"
                )
            result.unmapped.append(req)
            continue

        # Pick best candidate (highest score = most specific match)
        best = max(candidates, key=lambda c: c.score)
        used_pins.add(best.index)

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
                # For duplicates (e.g. multiple GND), find next best unused ground pin
                extra = _find_next_ground_or_duplicate(board, used_pins, req)
                if extra:
                    used_pins.add(extra.index)
                    result.assignments.append(PinAssignment(
                        net_name=req.net_name,
                        pin_name=extra.pin.name,
                        pin_index=extra.index,
                        score=extra.score,
                    ))

    return result


@dataclass
class _Candidate:
    pin: DevBoardPin
    index: int
    score: float


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


def _role_to_capabilities(role: str, net_name: str) -> set[str]:
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
    needed = _role_to_capabilities(req.role, req.net_name)
    for idx, pin in enumerate(board.pins):
        if idx in used_pins:
            continue
        pin_caps = set(pin.capabilities) | set(pin.alternate_functions)
        if needed & pin_caps:
            score = _score_match(pin, needed & pin_caps, needed, req)
            return _Candidate(pin=pin, index=idx, score=score)
    return None
