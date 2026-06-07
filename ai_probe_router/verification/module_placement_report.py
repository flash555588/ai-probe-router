"""Report hierarchical module placement regions and component placements."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..models.module_placement import ModulePlacementResult


@dataclass
class ModulePlacementReport:
    result: ModulePlacementResult

    def summary_text(self) -> str:
        lines = [
            "=" * 96,
            "  AI Probe Router - Module Placement Report",
            "=" * 96,
            "",
        ]
        if self.result.skipped:
            lines.append(f"  Module placement: SKIPPED ({self.result.skip_reason})")
            lines.append("=" * 96)
            return "\n".join(lines)

        lines.extend([
            f"  Regions:     {len(self.result.plan.regions)}",
            f"  Components:  {len(self.result.plan.components)}",
            f"  Warnings:    {len(self.result.warnings)}",
            "",
            "  Regions:",
        ])
        for region in self.result.plan.regions:
            box = region.region
            lines.append(
                f"    - {region.module_id} {region.module_name} "
                f"anchor={region.anchor} "
                f"box=({box.min_x:.1f},{box.min_y:.1f})-({box.max_x:.1f},{box.max_y:.1f})"
            )
            if region.probe_zone is not None:
                pz = region.probe_zone
                lines.append(
                    f"      probe zone=({pz.min_x:.1f},{pz.min_y:.1f})-"
                    f"({pz.max_x:.1f},{pz.max_y:.1f})"
                )
            if region.connector_zone is not None:
                cz = region.connector_zone
                lines.append(
                    f"      connector zone=({cz.min_x:.1f},{cz.min_y:.1f})-"
                    f"({cz.max_x:.1f},{cz.max_y:.1f})"
                )

        if self.result.plan.components:
            lines.append("")
            lines.append("  Component Placements:")
            for comp in self.result.plan.components:
                near = f" near={comp.near_refdes}" if comp.near_refdes else ""
                lines.append(
                    f"    - {comp.module_id} {comp.refdes:<6} {comp.component_type:<20} "
                    f"{comp.placement_class:<10} ({comp.x:.1f}, {comp.y:.1f}){near}"
                )

        for title, items in (("Errors", self.result.errors), ("Warnings", self.result.warnings)):
            if items:
                lines.append("")
                lines.append(f"  {title}:")
                for item in items:
                    lines.append(f"    - {item}")

        lines.append("")
        lines.append("=" * 96)
        return "\n".join(lines)

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.summary_text(), encoding="utf-8")

