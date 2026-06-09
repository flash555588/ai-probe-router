#!/usr/bin/env python3
"""Run optional native KiCad schematic/PCB validation.

The command skips cleanly when ``kicad-cli`` is unavailable by default. Use
``--require-kicad`` for release CI jobs where native KiCad validation is a hard
gate.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from ai_probe_router.eda_adapters.kicad.sch_health import healthcheck_schematic


@dataclass(frozen=True)
class NativeCommand:
    label: str
    command: list[str]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "project_dir",
        nargs="?",
        type=Path,
        default=Path("."),
        help="KiCad project directory containing main.kicad_sch and main.kicad_pcb",
    )
    parser.add_argument("--schematic", default="main.kicad_sch")
    parser.add_argument("--pcb", default="main.kicad_pcb")
    parser.add_argument("--build-dir", type=Path, default=Path("build/kicad"))
    parser.add_argument(
        "--require-kicad",
        action="store_true",
        help="fail if kicad-cli is not installed",
    )
    args = parser.parse_args(argv)

    kicad_cli = shutil.which("kicad-cli")
    if kicad_cli is None:
        print("kicad-cli not installed; skipping native KiCad validation")
        return 1 if args.require_kicad else 0

    project_dir = args.project_dir.resolve()
    schematic = project_dir / args.schematic
    pcb = project_dir / args.pcb
    build_dir = project_dir / args.build_dir
    build_dir.mkdir(parents=True, exist_ok=True)

    report = healthcheck_schematic(schematic)
    for line in report.to_lines():
        if line:
            print(line)
    if not report.ok:
        return 1

    commands = [
        NativeCommand("version", [kicad_cli, "version"]),
        NativeCommand(
            "schematic netlist export",
            [
                kicad_cli,
                "sch",
                "export",
                "netlist",
                "--output",
                str(build_dir / "main.net"),
                "--format",
                "kicadsexpr",
                str(schematic),
            ],
        ),
        NativeCommand(
            "schematic ERC",
            [
                kicad_cli,
                "sch",
                "erc",
                "--output",
                str(build_dir / "erc.json"),
                "--format",
                "json",
                "--exit-code-violations",
                str(schematic),
            ],
        ),
        NativeCommand(
            "PCB DRC",
            [
                kicad_cli,
                "pcb",
                "drc",
                "--output",
                str(build_dir / "drc.json"),
                "--format",
                "json",
                "--schematic-parity",
                "--exit-code-violations",
                str(pcb),
            ],
        ),
    ]
    failed = False
    for command in commands:
        print("+ " + " ".join(command.command))
        completed = subprocess.run(command.command, cwd=project_dir, check=False)
        if completed.returncode != 0:
            print(f"{command.label} failed with exit code {completed.returncode}")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
