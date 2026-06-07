"""Report module bus allocation and conflicts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..models.module_graph import ModuleGraphResult


@dataclass
class BusReport:
    result: ModuleGraphResult

    def summary_text(self) -> str:
        groups = self.result.graph.bus_groups
        lines = [
            "=" * 80,
            "  AI Probe Router - Bus Utilization Report",
            "=" * 80,
            "",
            f"  Bus groups: {len(groups)}",
            "",
        ]
        if not groups:
            lines.append("  No shared buses requested.")
        for group in groups:
            lines.append(f"  {group.bus_type.upper()}:")
            lines.append(f"    modules: {', '.join(group.modules) or 'none'}")
            if group.addresses:
                addr = ", ".join(
                    f"{module}={address}"
                    for module, address in sorted(group.addresses.items())
                )
                lines.append(f"    addresses: {addr}")
            if group.bus_type == "i2c":
                status = "covered" if group.pullup_covered else "missing"
                lines.append(f"    pull-ups: {status}")
            for conflict in group.conflicts:
                lines.append(f"    conflict: {conflict}")
        lines.append("")
        lines.append("=" * 80)
        return "\n".join(lines)

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.summary_text(), encoding="utf-8")

