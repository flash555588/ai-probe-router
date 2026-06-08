"""Module library preflight validation models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModuleLibraryPreflightIssue:
    severity: str
    path: str
    message: str


@dataclass
class ModuleLibraryPreflightResult:
    library_dirs: list[str] = field(default_factory=list)
    module_count: int = 0
    implementation_count: int = 0
    component_count: int = 0
    issues: list[ModuleLibraryPreflightIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[str]:
        return [
            _format_issue(issue)
            for issue in self.issues
            if issue.severity == "error"
        ]

    @property
    def warnings(self) -> list[str]:
        return [
            _format_issue(issue)
            for issue in self.issues
            if issue.severity == "warning"
        ]

    @property
    def ok(self) -> bool:
        return not self.errors


def _format_issue(issue: ModuleLibraryPreflightIssue) -> str:
    if issue.path:
        return f"{issue.path}: {issue.message}"
    return issue.message
