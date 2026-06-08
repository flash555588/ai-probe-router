"""Build footprint overlay items from PR6 report data."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .coordinate_transform import BoardCoordinateFrame


class OverlaySeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class FootprintOverlayItem:
    module_name: str
    reference: str
    footprint: str
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    side: str
    severity: OverlaySeverity
    issue_codes: tuple[str, ...] = ()
    wx: float = 0.0
    wy: float = 0.0
    wz: float = 0.0


class FootprintOverlayBuilder:
    """Convert footprint preview report entries into overlay items."""

    def __init__(self, frame: BoardCoordinateFrame) -> None:
        self.frame = frame

    def build_items(
        self,
        footprint_data,
    ) -> list[FootprintOverlayItem]:
        if footprint_data is None:
            return []

        planned = getattr(footprint_data, "footprints", None)
        if planned is None:
            planned = getattr(footprint_data, "planned_footprints", [])
        issues = getattr(footprint_data, "issues", [])
        issues_by_ref = self._issues_by_reference(issues)

        items: list[FootprintOverlayItem] = []
        for fp in planned:
            ref = fp.reference
            issue_list = issues_by_ref.get(ref, [])
            issue_codes = tuple(i.code for i in issue_list)
            severity = self._severity_for_issues(issue_list)

            wx, wy, wz = self.frame.pcb_to_world(fp.x_mm, fp.y_mm, fp.side)

            items.append(
                FootprintOverlayItem(
                    module_name=fp.module_name,
                    reference=ref,
                    footprint=fp.footprint,
                    x_mm=fp.x_mm,
                    y_mm=fp.y_mm,
                    width_mm=4.0,
                    height_mm=4.0,
                    side=fp.side,
                    severity=severity,
                    issue_codes=issue_codes,
                    wx=wx,
                    wy=wy,
                    wz=wz,
                )
            )

        return items

    @staticmethod
    def _issues_by_reference(issues) -> dict[str, list]:
        grouped: dict[str, list] = {}
        for issue in issues:
            ref = issue.reference
            if ref:
                grouped.setdefault(ref, []).append(issue)
        return grouped

    @staticmethod
    def _severity_for_issues(issue_list: list) -> OverlaySeverity:
        severities = {i.severity for i in issue_list}
        if "error" in severities:
            return OverlaySeverity.ERROR
        if "warning" in severities:
            return OverlaySeverity.WARNING
        return OverlaySeverity.INFO
