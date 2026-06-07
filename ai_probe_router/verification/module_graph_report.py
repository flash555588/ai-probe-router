"""Report concrete module graph instances and dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..models.module_graph import ModuleGraphResult


@dataclass
class ModuleGraphReport:
    result: ModuleGraphResult

    def summary_text(self) -> str:
        graph = self.result.graph
        lines = [
            "=" * 96,
            "  AI Probe Router - Module Graph Report",
            "=" * 96,
            "",
            f"  Instances:       {len(graph.instances)}",
            f"  Dependencies:    {len(graph.dependencies)}",
            f"  Errors:          {len(self.result.errors)}",
            f"  Warnings:        {len(self.result.warnings)}",
            f"  Ignored hints:   {len(self.result.ignored_hints)}",
            "",
        ]
        if graph.instances:
            lines.append("  Module Instances:")
            for instance in graph.instances:
                lines.append(
                    f"    - {instance.instance_id} {instance.name} "
                    f"({instance.module_type}) -> {instance.selected_implementation}"
                )
                versions = []
                if instance.version:
                    versions.append(f"module={instance.version}")
                if instance.selected_definition_version:
                    versions.append(f"definition={instance.selected_definition_version}")
                if instance.selected_implementation_version:
                    versions.append(
                        f"implementation={instance.selected_implementation_version}"
                    )
                if versions:
                    lines.append(f"      versions: {', '.join(versions)}")
                lines.append(f"      area: {instance.area_mm2:.1f}mm^2")
                if instance.target_nets:
                    lines.append(f"      target nets: {', '.join(instance.target_nets)}")
                if instance.generated_nets:
                    lines.append(f"      generated nets: {', '.join(instance.generated_nets)}")
                if instance.required_buses:
                    lines.append(f"      buses: {', '.join(instance.required_buses)}")
                if instance.voltage_domains or instance.rails:
                    power = instance.voltage_domains + instance.rails
                    lines.append(f"      power: {', '.join(power)}")
                if instance.refdes_pools:
                    refs = []
                    for role, values in sorted(instance.refdes_pools.items()):
                        refs.append(f"{role}={','.join(values)}")
                    lines.append(f"      refdes: {'; '.join(refs)}")
            lines.append("")

        if graph.dependencies:
            lines.append("  Dependencies:")
            for dep in graph.dependencies:
                arrow = "->" if dep.directed else "--"
                lines.append(
                    f"    - {dep.source_id} {arrow} {dep.target_id} ({dep.reason})"
                )
            lines.append("")

        for title, items in (
            ("Errors", self.result.errors),
            ("Warnings", self.result.warnings),
            ("Ignored AI Hints", self.result.ignored_hints),
        ):
            if items:
                lines.append(f"  {title}:")
                for item in items:
                    lines.append(f"    - {item}")
                lines.append("")

        lines.append("=" * 96)
        return "\n".join(lines)

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.summary_text(), encoding="utf-8")
