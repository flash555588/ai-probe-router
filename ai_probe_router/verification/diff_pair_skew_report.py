"""Diff pair skew report: verifies trace length matching for differential pairs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..models.probe import ProbeRequirement
from .report import CoverageReport


@dataclass
class DiffPairSkewRow:
    net_a: str
    net_b: str
    length_a_mm: float
    length_b_mm: float
    skew_mm: float
    skew_pct: float
    ok: bool


@dataclass
class DiffPairSkewReport:
    pairs: list[DiffPairSkewRow] = field(default_factory=list)
    max_skew_mm: float = 0.5
    max_skew_pct: float = 5.0

    def ok(self) -> bool:
        return all(p.ok for p in self.pairs)

    def summary_text(self) -> str:
        lines = [
            "=" * 60,
            "DIFFERENTIAL PAIR SKEW REPORT",
            "=" * 60,
            f"Thresholds: ±{self.max_skew_mm} mm or ±{self.max_skew_pct}%",
            "",
        ]
        if not self.pairs:
            lines.append("No differential pairs configured.")
            return "\n".join(lines)

        for p in self.pairs:
            status = "PASS" if p.ok else "FAIL"
            lines.append(
                f"  {p.net_a} ↔ {p.net_b}: "
                f"{p.length_a_mm:.2f} mm vs {p.length_b_mm:.2f} mm "
                f"(skew {p.skew_mm:+.2f} mm / {p.skew_pct:+.1f}%) [{status}]"
            )
        lines.append("")
        lines.append(f"Overall: {'PASS' if self.ok() else 'FAIL'}")
        return "\n".join(lines)

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.summary_text(), encoding="utf-8")


def generate_diff_pair_skew_report(
    coverage: CoverageReport,
    reqs: list[ProbeRequirement],
    max_skew_mm: float = 0.5,
    max_skew_pct: float = 5.0,
) -> DiffPairSkewReport:
    """Compare trace lengths for each configured differential pair."""
    report = DiffPairSkewReport(max_skew_mm=max_skew_mm, max_skew_pct=max_skew_pct)

    # Build length lookup from coverage entries
    length_by_net: dict[str, float] = {
        e.net_name: e.trace_length_mm for e in coverage.entries
    }

    # Find unique pairs (avoid duplicates)
    seen: set[frozenset[str]] = set()
    for req in reqs:
        if not req.pair_net_name:
            continue
        pair_key = frozenset({req.net_name, req.pair_net_name})
        if pair_key in seen:
            continue
        seen.add(pair_key)

        len_a = length_by_net.get(req.net_name, 0.0)
        len_b = length_by_net.get(req.pair_net_name, 0.0)
        avg_len = (len_a + len_b) / 2 if (len_a + len_b) > 0 else 1.0
        skew_mm = len_a - len_b
        skew_pct = (skew_mm / avg_len) * 100 if avg_len > 0 else 0.0

        ok = abs(skew_mm) <= max_skew_mm or abs(skew_pct) <= max_skew_pct
        report.pairs.append(DiffPairSkewRow(
            net_a=req.net_name,
            net_b=req.pair_net_name,
            length_a_mm=len_a,
            length_b_mm=len_b,
            skew_mm=skew_mm,
            skew_pct=skew_pct,
            ok=ok,
        ))

    return report
