"""Run KiCad CLI for ERC/DRC checks."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CheckResult:
    ok: bool | None
    violations: list[dict] = field(default_factory=list)
    raw_output: str = ""
    error: str = ""


def find_kicad_cli() -> str | None:
    for name in ("kicad-cli", "kicad-cli.exe"):
        path = shutil.which(name)
        if path:
            return path
    candidates = [
        Path("C:/Program Files/KiCad/9.0/bin/kicad-cli.exe"),
        Path("C:/Program Files/KiCad/8.0/bin/kicad-cli.exe"),
        Path("/usr/bin/kicad-cli"),
        Path("/usr/local/bin/kicad-cli"),
        Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def run_erc(schematic_path: str | Path, output_dir: str | Path | None = None) -> CheckResult:
    cli = find_kicad_cli()
    if cli is None:
        return CheckResult(ok=None, error="kicad-cli not found")
    sch = Path(schematic_path)
    out_dir = Path(output_dir) if output_dir else sch.parent
    report = out_dir / (sch.stem + "_erc.json")
    cmd = [cli, "sch", "erc", "--format", "json", "--output", str(report), str(sch)]
    return _run(cmd, report)


def run_drc(pcb_path: str | Path, output_dir: str | Path | None = None) -> CheckResult:
    cli = find_kicad_cli()
    if cli is None:
        return CheckResult(ok=None, error="kicad-cli not found")
    pcb = Path(pcb_path)
    out_dir = Path(output_dir) if output_dir else pcb.parent
    report = out_dir / (pcb.stem + "_drc.json")
    cmd = [cli, "pcb", "drc", "--format", "json", "--output", str(report), str(pcb)]
    return _run(cmd, report)


def _run(cmd: list[str], report_path: Path) -> CheckResult:
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
        )
    except FileNotFoundError:
        return CheckResult(ok=None, error=f"Command not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        return CheckResult(ok=None, error="kicad-cli timed out")

    violations: list[dict] = []
    if report_path.exists():
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
            violations = data.get("violations", data.get("errors", []))
        except (json.JSONDecodeError, KeyError):
            pass

    ok = proc.returncode == 0 and len(violations) == 0
    return CheckResult(
        ok=ok,
        violations=violations,
        raw_output=proc.stdout + proc.stderr,
        error="" if ok else proc.stderr.strip(),
    )
