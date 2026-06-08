"""Severity filter state for the plugin shell."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SeverityFilterState:
    show_error: bool = True
    show_warning: bool = True
    show_info: bool = True

    def allows(self, severity: str) -> bool:
        s = severity.lower()
        if s == "error":
            return self.show_error
        if s == "warning":
            return self.show_warning
        if s == "info":
            return self.show_info
        return True
