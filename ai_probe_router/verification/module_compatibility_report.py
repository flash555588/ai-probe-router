"""Report module version compatibility and BOM substitution metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..models.module_compatibility import (
    ModuleCompatibilityResult,
    ModuleCompatibilityRow,
)
from ..models.module_graph import ModuleGraphResult, ModuleInstance


def analyze_module_compatibility(
    graph_result: ModuleGraphResult,
) -> ModuleCompatibilityResult:
    result = ModuleCompatibilityResult()

    for instance in graph_result.graph.instances:
        _check_instance_versions(instance, result)
        if not instance.components:
            result.warnings.append(
                f"{instance.instance_id}/{instance.name} has no component rows"
            )
            continue
        for component in instance.components:
            row = ModuleCompatibilityRow(
                module_id=instance.instance_id,
                module_name=instance.name,
                module_type=instance.module_type,
                module_version=instance.version,
                requested_version=instance.requested_version,
                definition_version=instance.selected_definition_version,
                implementation=instance.selected_implementation,
                implementation_version=instance.selected_implementation_version,
                component_role=component.role,
                component_type=component.type,
                component_version=component.version,
                chip=component.chip,
                chip_version=component.chip_version,
                package_options=list(component.package_options),
                footprint_version=component.footprint_version,
                alternate_chips=list(component.alternate_chips),
                alternate_footprints=list(component.alternate_footprints),
            )
            _grade_component(instance, row, result)
            result.rows.append(row)

    for error in graph_result.errors:
        if "requested module version" in error:
            result.errors.append(error)
    return result


def _check_instance_versions(
    instance: ModuleInstance,
    result: ModuleCompatibilityResult,
) -> None:
    if not instance.version:
        result.warnings.append(
            f"{instance.instance_id}/{instance.name} has no module version metadata"
        )
    if not instance.selected_implementation_version:
        result.warnings.append(
            f"{instance.instance_id}/{instance.name} implementation "
            "has no version metadata"
        )


def _grade_component(
    instance: ModuleInstance,
    row: ModuleCompatibilityRow,
    result: ModuleCompatibilityResult,
) -> None:
    if row.chip and not row.chip_version:
        row.notes.append("chip version not specified")
    if row.package_options and not row.footprint_version:
        row.notes.append("footprint version not specified")
    if row.chip and not row.alternate_chips:
        row.notes.append("no alternate chip listed")
    if row.package_options and not row.alternate_footprints:
        row.notes.append("no alternate footprint listed")

    if row.notes:
        row.status = "review"
        result.warnings.append(
            f"{instance.instance_id}/{instance.name} {row.component_type}: "
            + "; ".join(row.notes)
        )


@dataclass
class ModuleCompatibilityReport:
    result: ModuleCompatibilityResult

    def summary_text(self) -> str:
        lines = [
            "=" * 96,
            "  AI Probe Router - Module Compatibility Report",
            "=" * 96,
            "",
            f"  Rows:      {len(self.result.rows)}",
            f"  Errors:    {len(self.result.errors)}",
            f"  Warnings:  {len(self.result.warnings)}",
            "",
        ]

        if self.result.rows:
            lines.append("  Compatibility Matrix:")
            for row in self.result.rows:
                versions = _version_summary(row)
                lines.append(
                    f"    - {row.module_id} {row.module_name} "
                    f"{row.component_type} [{row.status}] {versions}"
                )
                chip = _chip_summary(row)
                if chip:
                    lines.append(f"      chip: {chip}")
                footprints = _footprint_summary(row)
                if footprints:
                    lines.append(f"      footprints: {footprints}")
                if row.notes:
                    lines.append(f"      notes: {'; '.join(row.notes)}")
            lines.append("")

        for title, items in (
            ("Errors", self.result.errors),
            ("Warnings", self.result.warnings),
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


def _version_summary(row: ModuleCompatibilityRow) -> str:
    module = row.module_version or "unversioned-module"
    implementation = row.implementation_version or "unversioned-implementation"
    component = row.component_version or "unversioned-component"
    return f"module={module} impl={implementation} component={component}"


def _chip_summary(row: ModuleCompatibilityRow) -> str:
    if not row.chip:
        return ""
    version = row.chip_version or "unversioned"
    alternates = ", ".join(row.alternate_chips) or "none"
    return f"{row.chip} ({version}); alternates: {alternates}"


def _footprint_summary(row: ModuleCompatibilityRow) -> str:
    if not row.package_options and not row.alternate_footprints:
        return ""
    selected = ", ".join(row.package_options) or "unspecified"
    version = row.footprint_version or "unversioned"
    alternates = ", ".join(row.alternate_footprints) or "none"
    return f"{selected} ({version}); alternates: {alternates}"
