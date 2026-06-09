"""Testpoint coverage and verification report generator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..models.net import NetRole


@dataclass
class NetCoverage:
    net_name: str
    role: NetRole
    required: bool
    has_testpoint: bool
    probe_x: float = 0.0
    probe_y: float = 0.0
    side: str = "top"
    review_required: bool = False
    trace_width_mm: float = 0.15
    clearance_mm: float = 0.15
    route_status: str = "not_attempted"
    routed_connections: int = 0
    total_connections: int = 0
    trace_length_mm: float = 0.0
    route_bends: int = 0
    routing_notes: list[str] = field(default_factory=list)
    placement_warnings: list[str] = field(default_factory=list)


@dataclass
class CoverageReport:
    run_id: str = ""
    total_nets_requested: int = 0
    covered: int = 0
    missing: int = 0
    entries: list[NetCoverage] = field(default_factory=list)
    erc_ok: bool | None = None
    drc_ok: bool | None = None
    erc_violations: int = 0
    drc_violations: int = 0
    constraint_ok: bool | None = None
    constraint_violations: int = 0
    constraint_messages: list[str] = field(default_factory=list)
    routing_ok: bool | None = None
    routed_connections: int = 0
    unrouted_connections: int = 0
    routing_messages: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def coverage_pct(self) -> float:
        if self.total_nets_requested == 0:
            return 100.0
        return self.covered / self.total_nets_requested * 100

    def summary_text(self) -> str:
        lines = [
            "=" * 96,
            "  AI Probe Router - Testpoint Coverage Report",
            "=" * 96,
            "",
        ]
        if self.run_id:
            lines.append(f"  Run ID:           {self.run_id}")
        lines.extend([
            f"  Requested nets:   {self.total_nets_requested}",
            f"  Covered:          {self.covered}",
            f"  Missing:          {self.missing}",
            f"  Coverage:         {self.coverage_pct:.1f}%",
            "",
        ])
        total_routes = self.routed_connections + self.unrouted_connections
        if self.routing_ok is not None:
            status = "PASS" if self.routing_ok else "UNROUTED"
            lines.append(
                f"  Routing:          {status} "
                f"({self.routed_connections}/{total_routes} connections)"
            )
            for msg in self.routing_messages:
                lines.append(f"    - {msg}")
        else:
            lines.append("  Routing:          SKIPPED")
        if self.erc_ok is not None:
            status = "PASS" if self.erc_ok else f"FAIL ({self.erc_violations} violations)"
            lines.append(f"  ERC:              {status}")
        else:
            lines.append("  ERC:              SKIPPED")
        if self.drc_ok is not None:
            status = "PASS" if self.drc_ok else f"FAIL ({self.drc_violations} violations)"
            lines.append(f"  DRC:              {status}")
        else:
            lines.append("  DRC:              SKIPPED")
        if self.constraint_ok is not None:
            status = "PASS" if self.constraint_ok else f"FAIL ({self.constraint_violations} issues)"
            lines.append(f"  Constraints:      {status}")
            for msg in self.constraint_messages:
                lines.append(f"    - {msg}")
        lines.append("")

        review_nets = [e.net_name for e in self.entries if e.review_required]
        if review_nets:
            lines.append("  Human review required:")
            for name in review_nets:
                lines.append(f"    - {name}")
            lines.append("")

        lines.append("  Net Details:")
        lines.append("  " + "-" * 96)
        header = (
            f"  {'Net':<20} {'Role':<14} {'Req':>3}  "
            f"{'Placed':>6}  {'Route':>7}  {'Review':>6}  "
            f"{'Trace':>5}  {'Clr':>4}  {'Location'}"
        )
        lines.append(header)
        lines.append("  " + "-" * 96)
        for e in self.entries:
            loc = f"({e.probe_x:.1f}, {e.probe_y:.1f}) {e.side}" if e.has_testpoint else "n/a"
            placed = "YES" if e.has_testpoint else "NO"
            route = (
                f"{e.routed_connections}/{e.total_connections}"
                if e.total_connections else e.route_status
            )
            req = "YES" if e.required else "no"
            rev = "YES" if e.review_required else "no"
            lines.append(
                f"  {e.net_name:<20} {e.role.name:<14} {req:>3}  "
                f"{placed:>6}  {route:>7}  {rev:>6}  {e.trace_width_mm:>5.2f}  "
                f"{e.clearance_mm:>4.2f}  {loc}"
            )
            if e.route_bends:
                lines.append(f"    route: {e.route_bends} bend(s)")
            for note in e.routing_notes:
                lines.append(f"    route: {note}")
            for warn in e.placement_warnings:
                lines.append(f"    warn: {warn}")
        lines.append("")
        lines.append("=" * 96)
        return "\n".join(lines)

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.summary_text(), encoding="utf-8")
