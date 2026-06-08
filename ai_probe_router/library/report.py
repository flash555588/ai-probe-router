"""Library check report formatting."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .checker import ValidationIssue, ValidationSeverity


@dataclass
class LibraryCheckReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    @property
    def valid(self) -> bool:
        return len(self.errors) == 0

    @property
    def exit_code(self) -> int:
        if self.errors:
            return 3
        if self.warnings:
            return 2
        return 0

    def to_text(self) -> str:
        lines = ["Library Check Report", "=" * 40, ""]
        if not self.issues:
            lines.append("All checks passed.")
            return "\n".join(lines)

        lines.append(f"Total issues: {len(self.issues)}")
        lines.append(f"  Errors:   {len(self.errors)}")
        lines.append(f"  Warnings: {len(self.warnings)}")
        lines.append("")

        for issue in self.issues:
            prefix = "ERROR" if issue.severity == ValidationSeverity.ERROR else "WARN"
            loc = f"{issue.file.name}"
            field = f" [{issue.field}]" if issue.field else ""
            lines.append(f"{prefix} [{issue.layer}] {loc}{field}: {issue.message}")

        lines.append("")
        if self.errors:
            lines.append("Result: INVALID")
        elif self.warnings:
            lines.append("Result: VALID_WITH_WARNINGS")
        else:
            lines.append("Result: VALID")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "exit_code": self.exit_code,
            "summary": {
                "total": len(self.issues),
                "errors": len(self.errors),
                "warnings": len(self.warnings),
            },
            "issues": [
                {
                    "severity": i.severity.value,
                    "layer": i.layer,
                    "file": str(i.file),
                    "field": i.field,
                    "message": i.message,
                }
                for i in self.issues
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def write(self, text_path: str | Path, json_path: str | Path | None = None) -> None:
        Path(text_path).write_text(self.to_text(), encoding="utf-8")
        if json_path is not None:
            Path(json_path).write_text(self.to_json(), encoding="utf-8")
