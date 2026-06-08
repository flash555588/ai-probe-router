"""Transactional file workflow for imported autorouter geometry."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from ..eda_adapters.kicad.pcb_parser import parse_pcb
from ..eda_adapters.kicad.pcb_writer import write_pcb
from .routing_validation import (
    RoutingValidationIssue,
    RoutingValidationResult,
    validate_routed_session,
)
from .ses_import import apply_routed_session
from .ses_net_resolver import RoutedSession, SesNetResolutionError, parse_ses_routes


@dataclass
class RouteImportTransactionResult:
    ok: bool
    input_path: str
    candidate_path: str
    final_path: str
    validation: RoutingValidationResult
    session: RoutedSession | None = None
    promoted: bool = False
    report_path: str = ""

    @property
    def errors(self) -> list[RoutingValidationIssue]:
        return self.validation.errors

    @property
    def warnings(self) -> list[RoutingValidationIssue]:
        return self.validation.warnings

    def summary_text(self) -> str:
        lines = [
            "=" * 96,
            "  AI Probe Router - Route Import Safety Report",
            "=" * 96,
            "",
            f"  Status:     {'PASS' if self.ok else 'BLOCKED'}",
            f"  Input:      {self.input_path}",
            f"  Candidate:  {self.candidate_path}",
            f"  Final:      {self.final_path}",
            f"  Promoted:   {'yes' if self.promoted else 'no'}",
            "",
        ]
        if self.session is not None:
            lines.extend([
                f"  Segments:   {len(self.session.segments)}",
                f"  Vias:       {len(self.session.vias)}",
                "",
            ])
            if self.session.warnings:
                lines.append("  Parser warnings:")
                for warning in self.session.warnings:
                    lines.append(f"    - {warning}")
                lines.append("")
        if not self.validation.issues:
            lines.append("  No route import validation issues were reported.")
        else:
            lines.append("  Issues:")
            for issue in self.validation.issues:
                net = f" net={issue.net_name}" if issue.net_name else ""
                lines.append(
                    f"    - [{issue.severity.upper()}] {issue.code}{net}: {issue.message}"
                )
        lines.append("")
        lines.append("=" * 96)
        return "\n".join(lines)

    def write_report(self, path: str | Path) -> None:
        report_path = Path(path)
        report_path.write_text(self.summary_text(), encoding="utf-8")
        self.report_path = str(report_path)


def import_ses_transactional(
    input_pcb_path: str | Path,
    ses_path: str | Path,
    output_dir: str | Path,
    *,
    keep_candidate_on_failure: bool = True,
) -> RouteImportTransactionResult:
    input_path = Path(input_pcb_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = out_dir / f"{input_path.stem}.routed.candidate.kicad_pcb"
    final_path = out_dir / f"{input_path.stem}.routed.kicad_pcb"

    shutil.copyfile(input_path, candidate_path)

    try:
        board = parse_pcb(input_path)
        session = parse_ses_routes(ses_path)
    except (OSError, ValueError, SesNetResolutionError) as exc:
        result = _blocked_result(
            input_path,
            candidate_path,
            final_path,
            "SES_IMPORT_PARSE_ERROR",
            str(exc),
        )
        if not keep_candidate_on_failure and candidate_path.exists():
            candidate_path.unlink()
        return result

    validation = validate_routed_session(session, board)
    if not validation.ok:
        return RouteImportTransactionResult(
            ok=False,
            input_path=str(input_path),
            candidate_path=str(candidate_path),
            final_path=str(final_path),
            validation=validation,
            session=session,
        )

    apply_routed_session(board, session)
    write_pcb(board, candidate_path)

    post_check = _post_import_check(candidate_path)
    if not post_check.ok:
        return RouteImportTransactionResult(
            ok=False,
            input_path=str(input_path),
            candidate_path=str(candidate_path),
            final_path=str(final_path),
            validation=post_check,
            session=session,
        )

    shutil.copyfile(candidate_path, final_path)
    return RouteImportTransactionResult(
        ok=True,
        input_path=str(input_path),
        candidate_path=str(candidate_path),
        final_path=str(final_path),
        validation=validation,
        session=session,
        promoted=True,
    )


def _post_import_check(candidate_path: Path) -> RoutingValidationResult:
    try:
        parse_pcb(candidate_path)
    except (OSError, ValueError) as exc:
        return RoutingValidationResult(
            ok=False,
            issues=[
                RoutingValidationIssue(
                    severity="error",
                    code="ROUTE_CONNECTIVITY_FAILED",
                    message=f"candidate PCB could not be parsed after import: {exc}",
                )
            ],
        )
    return RoutingValidationResult(ok=True)


def _blocked_result(
    input_path: Path,
    candidate_path: Path,
    final_path: Path,
    code: str,
    message: str,
) -> RouteImportTransactionResult:
    return RouteImportTransactionResult(
        ok=False,
        input_path=str(input_path),
        candidate_path=str(candidate_path),
        final_path=str(final_path),
        validation=RoutingValidationResult(
            ok=False,
            issues=[
                RoutingValidationIssue(
                    severity="error",
                    code=code,
                    message=message,
                )
            ],
        ),
    )
