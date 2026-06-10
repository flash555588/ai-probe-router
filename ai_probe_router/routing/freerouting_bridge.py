"""Bridge to FreeRouting autorouter.

Locates the FreeRouting executable (JAR or native binary), invokes it with
a DSN file, and waits for the resulting SES session file.

Usage::

    from ai_probe_router.routing.freerouting_bridge import run_freerouting
    result = run_freerouting("board.dsn", timeout_sec=300)
    if result.ses_path:
        import_ses(board, result.ses_path)
"""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from ai_probe_router.subprocess_utils import run_text_tool


@dataclass
class RoutingResult:
    ok: bool = False
    dsn_path: str = ""
    ses_path: str | None = None
    stdout: str = ""
    stderr: str = ""
    error: str = ""
    duration_sec: float = 0.0


def find_freerouting() -> str | None:
    """Locate FreeRouting executable or JAR."""
    # Native binary names
    for name in ("freerouting", "freerouting.exe", "FreeRouting.exe"):
        path = shutil.which(name)
        if path:
            return path

    # JAR file — common install locations
    jar_candidates = [
        Path.home() / ".local/share/freerouting/freerouting.jar",
        Path.home() / "freerouting/freerouting.jar",
        Path("/usr/share/freerouting/freerouting.jar"),
        Path("/usr/local/share/freerouting/freerouting.jar"),
        Path("C:/Program Files/FreeRouting/freerouting.jar"),
        Path("C:/Program Files (x86)/FreeRouting/freerouting.jar"),
    ]
    for c in jar_candidates:
        if c.exists():
            return str(c)

    # Generic JAR search near the java executable
    java_path = shutil.which("java")
    if java_path:
        java_dir = Path(java_path).parent
        for parent in [java_dir, java_dir.parent, java_dir.parent.parent]:
            jar = parent / "freerouting.jar"
            if jar.exists():
                return str(jar)
    return None


def _is_jar(path: str) -> bool:
    return path.lower().endswith(".jar")


def run_freerouting(
    dsn_path: str | Path,
    output_dir: str | Path | None = None,
    timeout_sec: float = 300.0,
) -> RoutingResult:
    """Run FreeRouting on *dsn_path* and return the result.

    FreeRouting CLI arguments (v1.9+):
      -de  <dsn file>   design input
      -do  <ses file>   session output
      -mp  <int>        optimization passes
      -dct <int>        thread count
    """
    dsn = Path(dsn_path).resolve()
    if not dsn.exists():
        return RoutingResult(error=f"DSN file not found: {dsn}")

    out_dir = Path(output_dir) if output_dir else dsn.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    ses = out_dir / (dsn.stem + ".ses")

    exe = find_freerouting()
    if exe is None:
        return RoutingResult(
            error="FreeRouting not found. Install it or place freerouting.jar in a known location.",
        )

    if _is_jar(exe):
        java = shutil.which("java")
        if java is None:
            return RoutingResult(error="java not found in PATH (required for FreeRouting JAR).")
        cmd = [
            java, "-jar", exe,
            "-de", str(dsn),
            "-do", str(ses),
            "-mp", "20",
        ]
    else:
        cmd = [
            exe,
            "-de", str(dsn),
            "-do", str(ses),
            "-mp", "20",
        ]

    start = time.time()
    try:
        proc = run_text_tool(
            cmd,
            capture_output=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return RoutingResult(
            error=f"FreeRouting timed out after {timeout_sec}s",
            duration_sec=time.time() - start,
        )
    except FileNotFoundError as exc:
        return RoutingResult(error=f"Failed to launch FreeRouting: {exc}")

    duration = time.time() - start
    result = RoutingResult(
        ok=proc.returncode == 0 and ses.exists(),
        dsn_path=str(dsn),
        ses_path=str(ses) if ses.exists() else None,
        stdout=proc.stdout,
        stderr=proc.stderr,
        duration_sec=duration,
    )

    if not result.ok:
        hints = []
        if proc.returncode != 0:
            hints.append(f"exit code {proc.returncode}")
        if not ses.exists():
            hints.append("SES file was not created")
        result.error = "; ".join(hints) if hints else "unknown error"

    return result


def route_board(
    board,
    dsn_path: str | Path,
    output_dir: str | Path | None = None,
    timeout_sec: float = 300.0,
):
    """High-level helper: export DSN, run FreeRouting, import SES."""
    from .dsn_export import export_dsn
    from .ses_import import import_ses

    export_dsn(board, dsn_path)
    result = run_freerouting(dsn_path, output_dir, timeout_sec)
    if result.ses_path:
        import_ses(board, result.ses_path)
    return result
