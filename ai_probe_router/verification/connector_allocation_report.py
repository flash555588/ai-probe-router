"""Report connector pin reservations and allocation diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..solvers.connector_allocator import ConnectorAllocationResult


@dataclass
class ConnectorAllocationReport:
    result: ConnectorAllocationResult
    run_id: str = ""

    def summary_text(self) -> str:
        r = self.result
        lines = [
            "=" * 72,
            "  AI Probe Router - Connector Allocation Report",
            "=" * 72,
            "",
        ]
        if self.run_id:
            lines.append(f"  Run ID:           {self.run_id}")
        lines.extend([
            f"  Connector:        {r.connector_type} "
            f"({r.rows} rows x {r.pins_per_row} pins)",
            f"  Strategy:         {r.strategy}",
            f"  Used pins:        {r.used_pins}",
            f"  Free pins:        {r.free_pins}",
            f"  Utilization:      {r.utilization_percent:.1f}%",
            f"  Spread span:      {r.spread_span}",
            f"  Status:           {'OK' if r.ok else 'BLOCKED'}",
            "",
            "  Pin reservations:",
            "  " + "-" * 70,
            f"  {'Idx':<5}{'Pin':<12}{'Row':<5}{'Col':<5}"
            f"{'Status':<10}{'Net':<20}{'Role':<12}",
            "  " + "-" * 70,
        ])
        for res in r.reservations:
            fixed_mark = " [fixed]" if res.fixed and not res.net_name else ""
            lines.append(
                f"  {res.pin_index:<5}{res.pin_name:<12}{res.row:<5}"
                f"{res.column:<5}{res.status:<10}{res.net_name:<20}"
                f"{res.role:<12}{fixed_mark}".rstrip()
            )
        if r.conflicts:
            lines.append("")
            lines.append("  Conflicts:")
            for c in r.conflicts:
                lines.append(
                    f"    - pin={c.pin_name} index={c.pin_index} nets={c.nets}"
                )
        if r.warnings:
            lines.append("")
            lines.append("  Warnings:")
            for w in r.warnings:
                lines.append(f"    {w}")
        if r.errors:
            lines.append("")
            lines.append("  Errors:")
            for e in r.errors:
                lines.append(f"    {e}")
        lines.append("")
        lines.append("=" * 72)
        return "\n".join(lines)

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.summary_text() + "\n", encoding="utf-8")
