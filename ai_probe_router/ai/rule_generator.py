"""Generate design-rule and constraint recommendations from classified nets.

This module bridges the net classifier with the constraint engine, producing
KiCad-compatible design rules and internal constraint objects that reflect
the electrical and manufacturing requirements of each net class.

Usage::

    from ai_probe_router.ai.rule_generator import generate_rules
    from ai_probe_router.ai.net_classifier import classify_nets

    roles = classify_nets(net_names)
    rules = generate_rules(roles, requirements)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models.constraints import Constraints
from ..models.net import NetRole, NetSubRole
from ..models.probe import ProbeRequirement


@dataclass
class NetRule:
    net_name: str
    role: NetRole
    trace_width_mm: float = 0.15
    clearance_mm: float = 0.15
    max_stub_length_mm: float | None = None
    differential_pair: bool = False
    impedance_ohms: float | None = None
    require_human_review: bool = False
    avoid_near_clocks: bool = False
    guard_ring_optional: bool = False
    duplicate_probe_count: int = 1
    allow_shared_contacts: bool = False
    review_reason: str = ""


@dataclass
class GeneratedRules:
    net_rules: list[NetRule] = field(default_factory=list)
    global_constraints: Constraints = field(default_factory=Constraints)
    review_gates: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = ["Generated Design Rules", "=" * 40]
        for r in self.net_rules:
            lines.append(
                f"{r.net_name:20s}  role={r.role.name:12s}  "
                f"width={r.trace_width_mm:.2f}mm  clearance={r.clearance_mm:.2f}mm"
            )
            if r.differential_pair:
                lines.append(f"  → differential pair, impedance={r.impedance_ohms}Ω")
            if r.require_human_review:
                lines.append(f"  → REVIEW REQUIRED: {r.review_reason}")
        if self.review_gates:
            lines.append("")
            lines.append("Human Review Gates:")
            for g in self.review_gates:
                lines.append(f"  - {g}")
        return "\n".join(lines)


def generate_rules(
    net_roles: dict[str, NetRole],
    requirements: list[ProbeRequirement] | None = None,
    base_constraints: Constraints | None = None,
    net_sub_roles: dict[str, set[NetSubRole]] | None = None,
) -> GeneratedRules:
    """Produce a *GeneratedRules* object from classified nets.

    *requirements* supplies per-net user overrides (current, duplicate count,
    pair relationships).  *base_constraints* seeds the global rule set.
    *net_sub_roles* provides fine-grained sub-role tags per net.
    """
    req_map = {r.net_name: r for r in (requirements or [])}
    sub_map = net_sub_roles or {}
    result = GeneratedRules()
    result.global_constraints = base_constraints or Constraints()

    for net_name, role in net_roles.items():
        req = req_map.get(net_name)
        subs = sub_map.get(net_name, set())
        rule = _rule_for_role(net_name, role, req, subs)
        result.net_rules.append(rule)
        if rule.require_human_review:
            result.review_gates.append(f"{net_name}: {rule.review_reason}")

    # Update global constraints from most restrictive net rule
    if result.net_rules:
        result.global_constraints.routing.min_clearance_mm = max(
            r.clearance_mm for r in result.net_rules
        )
        result.global_constraints.routing.power_trace_width_mm = max(
            (r.trace_width_mm for r in result.net_rules if r.role == NetRole.POWER),
            default=result.global_constraints.routing.power_trace_width_mm,
        )

    return result


def _rule_for_role(
    net_name: str,
    role: NetRole,
    req: ProbeRequirement | None,
    sub_roles: set[NetSubRole] | None = None,
) -> NetRule:
    """Map a net role to default geometric/electrical rules."""
    rule = NetRule(net_name=net_name, role=role)
    subs = sub_roles or set()

    # Defaults per role
    if role == NetRole.POWER:
        rule.trace_width_mm = 0.50
        rule.clearance_mm = 0.20
        rule.duplicate_probe_count = max(req.duplicate_probe_count if req else 0, 1)
        rule.allow_shared_contacts = True
    elif role == NetRole.GROUND:
        rule.trace_width_mm = 0.40
        rule.clearance_mm = 0.20
        rule.duplicate_probe_count = max(req.duplicate_probe_count if req else 0, 2)
        rule.allow_shared_contacts = True
    elif role == NetRole.DEBUG:
        rule.trace_width_mm = 0.15
        rule.clearance_mm = 0.15
        rule.max_stub_length_mm = 10.0
    elif role == NetRole.RESET:
        rule.trace_width_mm = 0.15
        rule.clearance_mm = 0.15
        rule.max_stub_length_mm = 5.0
    elif role == NetRole.COMMUNICATION:
        rule.trace_width_mm = 0.15
        rule.clearance_mm = 0.15
    elif role == NetRole.HIGH_SPEED:
        rule.trace_width_mm = 0.15
        rule.clearance_mm = 0.20
        rule.differential_pair = True
        rule.impedance_ohms = 90
        rule.require_human_review = True
        rule.review_reason = "high-speed net — verify impedance and length matching"
    elif role == NetRole.CLOCK:
        rule.trace_width_mm = 0.15
        rule.clearance_mm = 0.20
        rule.require_human_review = True
        rule.avoid_near_clocks = False  # it IS a clock
        rule.review_reason = "clock net — verify skew and termination"
    elif role == NetRole.ANALOG:
        rule.trace_width_mm = 0.20
        rule.clearance_mm = 0.20
        rule.require_human_review = True
        rule.guard_ring_optional = True
        rule.avoid_near_clocks = True
        rule.review_reason = "analog net — verify guard ring and noise coupling"
    elif role == NetRole.GPIO:
        rule.trace_width_mm = 0.15
        rule.clearance_mm = 0.15

    # Sub-role refinements
    if NetSubRole.STRAPPING_PIN in subs:
        rule.require_human_review = True
        rule.review_reason = (
            "strapping pin — probe capacitance may affect boot behavior"
        )
    if NetSubRole.ADC_INPUT in subs:
        rule.clearance_mm = max(rule.clearance_mm, 0.25)
        rule.avoid_near_clocks = True
        rule.guard_ring_optional = True
    if NetSubRole.SD_DATA in subs:
        if not rule.require_human_review:
            rule.require_human_review = True
            rule.review_reason = "SD data line — verify pull-up resistors present"
    if NetSubRole.BATTERY in subs:
        if not rule.require_human_review:
            rule.require_human_review = True
            rule.review_reason = "battery net — verify protection circuit present"
    if NetSubRole.AUDIO_ANALOG in subs:
        rule.avoid_near_clocks = True
        rule.clearance_mm = max(rule.clearance_mm, 0.25)
    if NetSubRole.I2S_CLOCK in subs:
        rule.clearance_mm = max(rule.clearance_mm, 0.20)

    # Apply user overrides from requirements
    if req:
        if req.current_ma > 0:
            # Widen trace for current capacity (very rough IPC-2221 approx)
            min_width = _width_for_current(req.current_ma)
            rule.trace_width_mm = max(rule.trace_width_mm, min_width)
            if req.current_ma > 500:
                rule.require_human_review = True
                rule.review_reason = (
                    f"high current ({req.current_ma} mA) — verify thermal and voltage drop"
                )
        if req.duplicate_probe_count > 0:
            rule.duplicate_probe_count = req.duplicate_probe_count

    return rule


def _width_for_current(current_ma: float) -> float:
    """Rough trace width estimate for 1-oz copper (mm)."""
    # IPC-2221 outer layer, 10°C rise, very conservative simplification
    current_a = current_ma / 1000.0
    return max(0.15, current_a * 0.5)


def to_kicad_design_rules(rules: GeneratedRules) -> list[dict]:
    """Convert generated rules to a KiCad net-class compatible representation."""
    classes: list[dict] = []
    for r in rules.net_rules:
        classes.append({
            "name": f"NET_{r.net_name}",
            "trace_width": r.trace_width_mm,
            "clearance": r.clearance_mm,
            "via_diameter": r.trace_width_mm + 0.3,
            "diff_pair_width": r.trace_width_mm if r.differential_pair else None,
            "diff_pair_gap": 0.15 if r.differential_pair else None,
        })
    return classes
