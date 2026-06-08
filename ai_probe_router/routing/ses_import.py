"""Safely import parsed Specctra/Electra SES routes into a Board."""

from __future__ import annotations

import uuid
from pathlib import Path

from ..models.board import Board
from .routing_validation import (
    RoutingValidationIssue,
    RoutingValidationResult,
    map_ses_layer,
    validate_routed_session,
)
from .ses_net_resolver import RoutedSession, SesNetResolutionError, parse_ses_routes


def import_ses(board: Board, path: str | Path) -> RoutingValidationResult:
    """Parse, validate, then append routed tracks/vias to a board.

    The board is mutated only after SES route objects pass validation. Imported
    items are assigned to existing KiCad net IDs and never silently fall back to
    net 0.
    """
    try:
        session = parse_ses_routes(path)
    except (OSError, ValueError, SesNetResolutionError) as exc:
        return RoutingValidationResult(
            ok=False,
            issues=[
                RoutingValidationIssue(
                    severity="error",
                    code="SES_IMPORT_PARSE_ERROR",
                    message=str(exc),
                )
            ],
        )
    validation = validate_routed_session(session, board)
    if not validation.ok:
        return validation
    apply_routed_session(board, session)
    return validation


def apply_routed_session(board: Board, session: RoutedSession) -> None:
    for segment in session.segments:
        net_id = board.nets[segment.net_name]
        layer = map_ses_layer(segment.layer)
        if layer is None:
            continue
        board.raw.append([
            "segment",
            ["start", str(segment.x1_mm), str(segment.y1_mm)],
            ["end", str(segment.x2_mm), str(segment.y2_mm)],
            ["width", str(segment.width_mm)],
            ["layer", layer],
            ["net", str(net_id)],
            ["uuid", str(uuid.uuid4())],
        ])

    for via in session.vias:
        net_id = board.nets[via.net_name]
        layers = [map_ses_layer(layer) for layer in via.layers]
        mapped_layers = [layer for layer in layers if layer is not None]
        if not mapped_layers:
            continue
        board.raw.append([
            "via",
            ["at", str(via.x_mm), str(via.y_mm)],
            ["size", str(via.diameter_mm or 0.8)],
            ["drill", str(via.drill_mm or 0.4)],
            ["layers"] + mapped_layers,
            ["net", str(net_id)],
            ["uuid", str(uuid.uuid4())],
        ])
