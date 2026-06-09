#!/usr/bin/env python3
"""Run native KiCad schematic/PCB validation and collect evidence.

The command skips cleanly when ``kicad-cli`` is unavailable by default. Use
``--require-kicad`` for CI jobs where native KiCad validation is a hard gate.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ai_probe_router.verification.native_validation_runner import (
    NativeValidationOptions,
    run_native_validation,
)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    project_root = (args.project_root or args.project_dir or Path(".")).resolve()
    run = run_native_validation(
        NativeValidationOptions(
            project_root=project_root,
            schematic=args.schematic,
            pcb=args.pcb,
            build_dir=args.build_dir,
            report_dir=args.report_dir,
            strict=args.strict,
            require_kicad=args.require_kicad,
            require_kicad_major=args.require_kicad_major or None,
            enable_erc=args.enable_erc,
            enable_drc=args.enable_drc,
            enable_parity=args.enable_parity,
            baseline=args.baseline,
            block_new_regressions=args.block_new_regressions,
        ),
        echo=True,
    )
    return run.return_code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "project_dir",
        nargs="?",
        type=Path,
        default=None,
        help="KiCad project directory containing main.kicad_sch and main.kicad_pcb",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="explicit KiCad project directory; overrides positional project_dir",
    )
    parser.add_argument("--schematic", default="main.kicad_sch")
    parser.add_argument("--pcb", default="main.kicad_pcb")
    parser.add_argument("--build-dir", type=Path, default=None)
    parser.add_argument("--report-dir", type=Path, default=None)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return non-zero when native checks report findings",
    )
    parser.add_argument(
        "--require-kicad",
        action="store_true",
        help="fail if kicad-cli is not installed",
    )
    parser.add_argument(
        "--require-kicad-major",
        type=int,
        default=9,
        help="required KiCad major version for hard validation; use 0 to disable",
    )
    parser.add_argument("--enable-erc", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--enable-drc", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--enable-parity",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="include schematic parity during PCB DRC",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="reviewed native-validation baseline JSON for regression comparison",
    )
    parser.add_argument(
        "--block-new-regressions",
        action="store_true",
        help="fail for new issue categories or increased baseline counts",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
