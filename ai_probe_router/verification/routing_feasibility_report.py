"""Report module-level routing corridor feasibility."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..routing.module_corridor import RoutingFeasibilityResult


@dataclass
class RoutingFeasibilityReport:
    result: RoutingFeasibilityResult

    def summary_text(self) -> str:
        lines = [
            "=" * 96,
            "  AI Probe Router - Routing Feasibility Report",
            "=" * 96,
            "",
        ]
        if self.result.skipped:
            lines.append(f"  Routing feasibility: SKIPPED ({self.result.skip_reason})")
            lines.append("=" * 96)
            return "\n".join(lines)

        lines.extend([
            f"  Corridors:          {len(self.result.corridors)}",
            f"  Congestion spots:   {len(self.result.congestion_hotspots)}",
            f"  Hard obstacles:     {self.result.hard_obstacle_count}",
            f"  Grid capacity:      {self.result.grid_capacity}",
            "",
            "  Corridors:",
            "  " + "-" * 96,
        ])
        for corridor in self.result.corridors:
            status = "OK" if corridor.ok else f"FAIL {corridor.message}"
            lines.append(
                f"  {corridor.source_id:<8} -> {corridor.target_id:<8} "
                f"{corridor.reason:<24} {status:<18} "
                f"len={corridor.length_mm:.1f} cost={corridor.total_cost:.1f} "
                f"cong={corridor.congestion_score:.1f} "
                f"cap={corridor.capacity_penalty:.1f} "
                f"obs={corridor.obstacle_penalty:.1f} "
                f"sens={corridor.sensitive_penalty:.1f}"
            )
        if self.result.congestion_hotspots:
            lines.append("")
            lines.append("  Congestion Hotspots:")
            for x, y, count in self.result.congestion_hotspots:
                lines.append(f"    - ({x:.1f}, {y:.1f}) used by {count} corridors")
        if self.result.warnings:
            lines.append("")
            lines.append("  Recommendations:")
            for warning in self.result.warnings:
                lines.append(f"    - {warning}")
        lines.append("")
        lines.append("=" * 96)
        return "\n".join(lines)

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.summary_text(), encoding="utf-8")
