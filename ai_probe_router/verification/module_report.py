"""Human-readable report for schema-v2 functional module planning."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..solvers.module_selector import ModuleSelectionResult


@dataclass
class ModuleReport:
    result: ModuleSelectionResult

    def summary_text(self) -> str:
        lines = [
            "=" * 96,
            "  AI Probe Router - Module Planning Report",
            "=" * 96,
            "",
            f"  Requested modules: {self.result.requested_count}",
            f"  Selected:          {len(self.result.selected)}",
            f"  Errors:            {len(self.result.errors)}",
            f"  Warnings:          {len(self.result.warnings)}",
            "",
        ]

        if self.result.selected:
            lines.append("  Selected Modules:")
            for selected in self.result.selected:
                module = selected.module
                impl = selected.implementation
                lines.append(
                    f"    - {module.name} ({module.type}) -> "
                    f"{selected.definition.name}/{impl.name}"
                )
                versions = []
                if module.version:
                    versions.append(f"requested={module.version}")
                if selected.definition.version:
                    versions.append(f"definition={selected.definition.version}")
                if impl.version:
                    versions.append(f"implementation={impl.version}")
                if versions:
                    lines.append(f"      versions: {', '.join(versions)}")
                component_summary = ", ".join(
                    f"{component.count}x {component.type}"
                    for component in impl.components
                )
                if component_summary:
                    lines.append(f"      components: {component_summary}")
                lines.append(
                    "      review: "
                    + ("required" if selected.review_required else "not required")
                )
                for reason in selected.reasons:
                    lines.append(f"      reason: {reason}")
                for rejection in selected.rejected:
                    lines.append(f"      rejected: {rejection}")
            lines.append("")

        if self.result.errors:
            lines.append("  Errors:")
            for error in self.result.errors:
                lines.append(f"    - {error}")
            lines.append("")

        if self.result.warnings:
            lines.append("  Warnings:")
            for warning in self.result.warnings:
                lines.append(f"    - {warning}")
            lines.append("")

        lines.append("=" * 96)
        return "\n".join(lines)

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.summary_text(), encoding="utf-8")
