"""Helpers for invoking external tools with deterministic text decoding."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any


def run_text_tool(
    cmd: Sequence[str | Path],
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Run an argv-style command and decode captured output as UTF-8.

    All call sites pass argument lists with ``shell=False`` so paths and user
    selections are never interpreted by a shell.
    """
    return subprocess.run(  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
        [str(part) for part in cmd],
        shell=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        **kwargs,
    )
