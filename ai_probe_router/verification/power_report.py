"""Report module power-domain usage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..models.module_graph import ModuleGraphResult


@dataclass
class PowerReport:
    result: ModuleGraphResult

    def summary_text(self) -> str:
        domains = self.result.graph.power_domains
        lines = [
            "=" * 80,
            "  AI Probe Router - Power Domain Report",
            "=" * 80,
            "",
            f"  Domains: {len(domains)}",
            "",
        ]
        if not domains:
            lines.append("  No module voltage domains or rails requested.")
        for domain in domains:
            budget = (
                f"{domain.max_current_ma:.1f}mA"
                if domain.max_current_ma else "unspecified"
            )
            lines.append(f"  {domain.domain_name}:")
            lines.append(f"    modules: {', '.join(domain.modules) or 'none'}")
            lines.append(f"    estimated load: {domain.current_ma:.1f}mA")
            lines.append(f"    budget: {budget}")
            for warning in domain.warnings:
                lines.append(f"    warning: {warning}")
        missing = [
            error for error in self.result.errors
            if "missing voltage domain" in error
        ]
        if missing:
            lines.append("")
            lines.append("  Missing Domains:")
            for error in missing:
                lines.append(f"    - {error}")
        lines.append("")
        lines.append("=" * 80)
        return "\n".join(lines)

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.summary_text(), encoding="utf-8")

