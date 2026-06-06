"""DRC/ERC repair agent: suggests fixes for common violations.

This module implements the "AI repair loop" described in pcb.txt §8.
It consumes ERC/DRC violation dictionaries and proposes concrete schematic
or layout changes, staying on the *suggestion* side of the AI/deterministic
boundary.

Usage::

    from ai_probe_router.ai.drc_repair_agent import suggest_fixes
    suggestions = suggest_fixes(drc_violations, board, schematic)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from ..models.board import Board, Schematic
from ..models.net import NetRole
from .net_classifier import classify_net


@dataclass
class RepairSuggestion:
    violation_type: str
    message: str
    net_name: str = ""
    suggested_action: str = ""
    confidence: str = "medium"  # low | medium | high
    auto_applicable: bool = False


@dataclass
class RepairReport:
    suggestions: list[RepairSuggestion] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"Repair Suggestions ({len(self.suggestions)})", "=" * 40]
        for s in self.suggestions:
            lines.append(f"[{s.confidence.upper()}] {s.violation_type}: {s.message}")
            if s.net_name:
                lines.append(f"  Net : {s.net_name}")
            lines.append(f"  Fix : {s.suggested_action}")
            lines.append("")
        return "\n".join(lines)


def suggest_fixes(
    violations: list[dict],
    board: Board | None = None,
    schematic: Schematic | None = None,
) -> RepairReport:
    """Return repair suggestions for a list of DRC/ERC violations."""
    report = RepairReport()
    for v in violations:
        sug = _suggest_for(v, board, schematic)
        if sug:
            report.suggestions.append(sug)
    return report


def _suggest_for(
    violation: dict,
    board: Board | None,
    schematic: Schematic | None,
) -> RepairSuggestion | None:
    vtype = violation.get("type", "").lower()
    desc = violation.get("description", violation.get("message", ""))
    net = violation.get("net", "")
    items = violation.get("items", [])
    pos = items[0].get("pos") if items and isinstance(items[0], dict) else None

    # Clearance / collision violations
    if "clearance" in desc.lower() or "clearance" in vtype:
        role = _net_role(net)
        action = _clearance_action_for_role(role, pos)
        return RepairSuggestion(
            violation_type=vtype,
            message=desc,
            net_name=net,
            suggested_action=action,
            confidence="high",
            auto_applicable=False,
        )

    if "collision" in desc.lower() or "overlap" in desc.lower():
        action = _collision_action(net, pos)
        return RepairSuggestion(
            violation_type=vtype,
            message=desc,
            net_name=net,
            suggested_action=action,
            confidence="high",
            auto_applicable=False,
        )

    # Unconnected / no-net violations
    if "unconnected" in desc.lower() or "no net" in desc.lower():
        nearby = _nearby_nets(pos, schematic)
        action = "Add net label or wire stub to connect the dangling pin."
        if nearby:
            action += f" Nearby nets on schematic: {', '.join(nearby)}."
        return RepairSuggestion(
            violation_type=vtype,
            message=desc,
            net_name=net,
            suggested_action=action,
            confidence="high",
            auto_applicable=True,
        )

    # Short-circuit / net merge
    if "short" in desc.lower() or "conflict" in desc.lower():
        nets = _extract_nets_from_items(items, net)
        role = _net_role(net)
        if role in {NetRole.GROUND, NetRole.POWER}:
            return RepairSuggestion(
                violation_type=vtype,
                message=desc,
                net_name=net,
                suggested_action=(
                    "Power/ground shorts may be intentional net ties; "
                    "verify with designer."
                ),
                confidence="low",
                auto_applicable=False,
            )
        action = (
            "Separate traces or add keepout to prevent unintended net merge."
        )
        if len(nets) >= 2:
            action = (
                f"Keep {nets[0]} and {nets[1]} separated; "
                "add keepout or reroute to prevent merge."
            )
        return RepairSuggestion(
            violation_type=vtype,
            message=desc,
            net_name=net,
            suggested_action=action,
            confidence="high",
            auto_applicable=False,
        )

    # Silkscreen / fabrication
    if "silk" in desc.lower():
        return RepairSuggestion(
            violation_type=vtype,
            message=desc,
            net_name=net,
            suggested_action=(
                "Shrink silkscreen text or move away from pad/solder mask opening."
            ),
            confidence="medium",
            auto_applicable=False,
        )

    if "drill" in desc.lower() or "annular" in desc.lower():
        return RepairSuggestion(
            violation_type=vtype,
            message=desc,
            net_name=net,
            suggested_action=(
                "Enlarge pad diameter or reduce drill size to meet "
                "annular ring rule."
            ),
            confidence="high",
            auto_applicable=False,
        )

    # Generic fallback
    return RepairSuggestion(
        violation_type=vtype,
        message=desc,
        net_name=net,
        suggested_action="Review violation in EDA tool and adjust placement or rules.",
        confidence="low",
        auto_applicable=False,
    )


def _net_role(net_name: str) -> NetRole:
    return classify_net(net_name) if net_name else NetRole.UNKNOWN


def _clearance_action_for_role(role: NetRole, pos: dict | None) -> str:
    base = (
        "Increase net class clearance or move probe pad farther from aggressor"
    )
    if pos:
        base += f" at ({pos.get('x')}, {pos.get('y')})"
    if role == NetRole.HIGH_SPEED:
        base += "; for high-speed nets also verify impedance and length matching."
    elif role == NetRole.CLOCK:
        base += "; for clock nets also check length matching and termination."
    elif role in {NetRole.POWER, NetRole.GROUND}:
        base += "; power/ground clearance violations may require wider thermal reliefs."
    else:
        base += "."
    return base


def _collision_action(net_name: str, pos: dict | None) -> str:
    action = "Re-run placement solver with larger component keepout"
    if net_name:
        action += f" for net '{net_name}'"
    if pos:
        action += f" at ({pos.get('x')}, {pos.get('y')})"
    action += "."
    return action


def _nearby_nets(pos: dict | None, schematic: Schematic | None) -> list[str]:
    if not pos or not schematic:
        return []
    px, py = pos.get("x", 0.0), pos.get("y", 0.0)
    nearby: list[tuple[float, str]] = []
    for lb in schematic.labels:
        lx = lb.get("x", 0.0)
        ly = lb.get("y", 0.0)
        dist = math.hypot(px - lx, py - ly)
        if dist < 10.0:
            nearby.append((dist, lb.get("name", "")))
    nearby.sort()
    return [name for _, name in nearby[:3] if name]


def _extract_nets_from_items(items: list[dict], fallback_net: str) -> list[str]:
    nets: list[str] = []
    for item in items:
        desc = item.get("description", "")
        for m in re.finditer(r"\[([^\]]+)\]", desc):
            candidate = m.group(1).strip()
            if candidate and candidate not in nets:
                nets.append(candidate)
    if fallback_net and fallback_net not in nets:
        nets.insert(0, fallback_net)
    return nets
