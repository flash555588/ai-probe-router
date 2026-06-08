#!/usr/bin/env python3
"""Healthcheck and optionally repair KiCad schematic files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ai_probe_router.eda_adapters.kicad.sch_health import (
    healthcheck_schematic,
    repair_schematic_file,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("schematic", type=Path)
    parser.add_argument("--repair", action="store_true", help="write a repaired schematic")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="repair destination; defaults to modifying the input file",
    )
    args = parser.parse_args(argv)

    if args.repair:
        repair_schematic_file(args.schematic, args.output)
        report_path = args.output or args.schematic
    else:
        report_path = args.schematic

    report = healthcheck_schematic(report_path)
    for line in report.to_lines():
        if line:
            print(line)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
