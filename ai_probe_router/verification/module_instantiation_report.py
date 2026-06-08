"""Report generated module schematic sheets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..synthesis.module_instantiator import ModuleInstantiationResult


@dataclass
class ModuleInstantiationReport:
    result: ModuleInstantiationResult

    def summary_text(self) -> str:
        lines = [
            "=" * 96,
            "  AI Probe Router - Module Instantiation Report",
            "=" * 96,
            "",
        ]
        if self.result.run_id:
            lines.append(f"  Run ID:           {self.result.run_id}")
            lines.append("")
        if self.result.skipped:
            lines.append(f"  Module instantiation: SKIPPED ({self.result.skip_reason})")
            lines.append("=" * 96)
            return "\n".join(lines)

        lines.extend([
            f"  Generated sheets: {len(self.result.sheets)}",
            f"  Warnings:         {len(self.result.warnings)}",
            "",
        ])
        for sheet in self.result.sheets:
            lines.append(
                f"    - {sheet.module_id} {sheet.module_name}: {sheet.sheet_file}"
            )
            if sheet.pins:
                lines.append(f"      pins: {', '.join(sheet.pins)}")
        if self.result.warnings:
            lines.append("")
            lines.append("  Warnings:")
            for warning in self.result.warnings:
                lines.append(f"    - {warning}")
        lines.append("")
        lines.append("=" * 96)
        return "\n".join(lines)

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.summary_text(), encoding="utf-8")
