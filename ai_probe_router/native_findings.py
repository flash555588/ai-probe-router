"""Shared native KiCad finding fingerprint and grouping helpers."""

from __future__ import annotations

import hashlib
from typing import Any


def finding_fingerprint(finding: dict[str, Any]) -> str:
    parts = [
        finding.get("source", ""),
        finding.get("severity", ""),
        finding.get("type", ""),
        finding.get("message", ""),
        finding.get("item", ""),
        finding.get("path", ""),
    ]
    raw = "\x1f".join(str(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def group_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for finding in findings:
        key = (
            str(finding.get("source", "")),
            str(finding.get("severity", "")),
            str(finding.get("type", "")),
            str(finding.get("message", "")),
        )
        group = grouped.setdefault(
            key,
            {
                "source": key[0],
                "severity": key[1],
                "type": key[2],
                "message": key[3],
                "count": 0,
                "examples": [],
            },
        )
        group["count"] += 1
        if len(group["examples"]) < 3:
            group["examples"].append(finding)
    return sorted(
        grouped.values(),
        key=lambda row: (-int(row["count"]), row["source"], row["type"], row["message"]),
    )
