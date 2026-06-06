"""Manufacturing output readiness report."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..models.board import Board
from .report import CoverageReport


@dataclass
class ManufacturingReport:
    board_outline_ok: bool = False
    board_size_mm: tuple[float, float] = (0.0, 0.0)
    testpoint_coverage_pct: float = 0.0
    fiducial_count: int = 0
    tooling_hole_count: int = 0
    keepout_zone_count: int = 0
    review_gate_count: int = 0
    net_class_summary: dict[str, int] = field(default_factory=dict)

    def summary_text(self) -> str:
        w, h = self.board_size_mm
        lines = [
            "=" * 60,
            "  Manufacturing Output Readiness Report",
            "=" * 60,
            "",
            f"  Board outline:     {'OK' if self.board_outline_ok else 'MISSING'}",
            f"  Board size:        {w:.1f} x {h:.1f} mm",
            f"  Testpoint coverage: {self.testpoint_coverage_pct:.1f}%",
            f"  Fiducials:         {self.fiducial_count}",
            f"  Tooling holes:     {self.tooling_hole_count}",
            f"  Keepout zones:     {self.keepout_zone_count}",
            f"  Review gates:      {self.review_gate_count}",
            "",
            "  Net Class Summary:",
            "  " + "-" * 56,
        ]
        for role_name, count in sorted(self.net_class_summary.items()):
            lines.append(f"    {role_name:<20} {count:>3} nets")
        lines.append("")
        ready = (
            self.board_outline_ok
            and self.testpoint_coverage_pct >= 100.0
            and self.review_gate_count == 0
        )
        lines.append(f"  Manufacturing ready: {'YES' if ready else 'NO'}")
        lines.append("=" * 60)
        return "\n".join(lines)

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.summary_text(), encoding="utf-8")


def generate_manufacturing_report(
    board: Board | None,
    coverage: CoverageReport,
) -> ManufacturingReport:
    report = ManufacturingReport()
    report.testpoint_coverage_pct = coverage.coverage_pct
    report.review_gate_count = sum(1 for e in coverage.entries if e.review_required)

    if board is not None:
        bounds = board.board_bounds()
        report.board_outline_ok = bounds is not None
        if bounds:
            report.board_size_mm = (bounds.width, bounds.height)

        for node in board.raw:
            if not (isinstance(node, list) and node[0] == "footprint"):
                continue
            ref = ""
            for child in node[1:]:
                if (
                    isinstance(child, list)
                    and child[0] == "property"
                    and child[1] == "Reference"
                ):
                    ref = child[2]
                    break
            if ref.startswith("FID"):
                report.fiducial_count += 1
            elif ref.startswith("TH"):
                report.tooling_hole_count += 1

        for node in board.raw:
            if isinstance(node, list) and node[0] == "zone":
                # Count only keepout zones, not copper pours
                if any(
                    isinstance(child, list) and child[0] == "keepout"
                    for child in node[1:]
                ):
                    report.keepout_zone_count += 1

    class_counts: dict[str, int] = {}
    for e in coverage.entries:
        name = e.role.name
        class_counts[name] = class_counts.get(name, 0) + 1
    report.net_class_summary = class_counts

    return report
