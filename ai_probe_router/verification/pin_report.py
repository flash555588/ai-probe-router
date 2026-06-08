"""Pin-mapping report generator for Phase 2."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..solvers.pin_mapper import MappingResult


@dataclass
class PinMapReport:
    board_name: str
    result: MappingResult
    output_path: str | Path = ""

    def summary_text(self) -> str:
        lines = [
            "=" * 72,
            "  AI Probe Router — Pin Mapping Report",
            "=" * 72,
            "",
            f"  Development Board: {self.board_name}",
            f"  Assigned:          {len(self.result.assignments)}",
            f"  Unmapped:          {len(self.result.unmapped)}",
            f"  Errors:            {len(self.result.errors)}",
            "",
        ]
        if self.result.errors:
            lines.append("  Errors:")
            for e in self.result.errors:
                lines.append(f"    - {e}")
            lines.append("")
        if self.result.warnings:
            lines.append("  Warnings:")
            for warning in self.result.warnings:
                lines.append(f"    - {warning}")
            lines.append("")
        lines.append("  Pin Assignments:")
        lines.append("  " + "-" * 68)
        lines.append(f"  {'Net':<20} {'Pin':<15} {'Index':>5}  {'Score':>6}")
        lines.append("  " + "-" * 68)
        for a in self.result.assignments:
            lines.append(
                f"  {a.net_name:<20} {a.pin_name:<15} {a.pin_index:>5}  {a.score:>6.1f}"
            )
        if self.result.unmapped:
            lines.append("")
            lines.append("  Unmapped Nets:")
            for u in self.result.unmapped:
                lines.append(f"    - {u.net_name} (role={u.role}, required={u.required})")
        lines.append("")
        lines.append("=" * 72)
        return "\n".join(lines)

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.summary_text(), encoding="utf-8")
