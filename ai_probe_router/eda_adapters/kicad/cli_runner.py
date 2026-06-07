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
        Path("C:/Program Files/KiCad/10.0/bin/kicad-cli.exe"),
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
            cmd, capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
    except FileNotFoundError:
        return CheckResult(ok=None, error=f"Command not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        return CheckResult(ok=None, error="kicad-cli timed out")

    violations: list[dict] = []
    report_loaded = False
    if report_path.exists():
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
            reported = data.get("violations", data.get("errors", []))
            reported += data.get("unconnected_items", [])
            violations = [
                v for v in reported
                if v.get("severity", "error") == "error"
                and v.get("type") not in ("lib_footprint_mismatch", "lib_footprint_issues")
            ]
            report_loaded = True
        except (json.JSONDecodeError, KeyError):
            pass

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    if report_loaded:
        ok = len(violations) == 0
        error = ""
    elif proc.returncode == 0:
        ok = True
        error = ""
    else:
        ok = False
        error = stderr.strip() or f"kicad-cli exited with code {proc.returncode}"

    return CheckResult(
        ok=ok,
        violations=violations,
        raw_output=stdout + stderr,
        error=error,
    )


def export_gerbers(pcb_path: str | Path, output_dir: str | Path) -> CheckResult:
    cli = find_kicad_cli()
    if cli is None:
        return CheckResult(ok=None, error="kicad-cli not found")
    cmd = [cli, "pcb", "export", "gerbers", "-o", str(output_dir), str(pcb_path)]
    return _run(cmd, Path(output_dir) / "gerber_export.log")


def export_drill(pcb_path: str | Path, output_dir: str | Path) -> CheckResult:
    cli = find_kicad_cli()
    if cli is None:
        return CheckResult(ok=None, error="kicad-cli not found")
    cmd = [cli, "pcb", "export", "drill", "-o", str(output_dir), str(pcb_path)]
    return _run(cmd, Path(output_dir) / "drill_export.log")


def export_pos(pcb_path: str | Path, output_file: str | Path) -> CheckResult:
    cli = find_kicad_cli()
    if cli is None:
        return CheckResult(ok=None, error="kicad-cli not found")
    cmd = [
        cli, "pcb", "export", "pos", "-o", str(output_file),
        "--side", "both", "--format", "csv", "--units", "mm",
        str(pcb_path),
    ]
    return _run(cmd, Path(output_file).parent / "pos_export.log")
