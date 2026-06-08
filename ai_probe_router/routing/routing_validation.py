"""Validation for imported autorouter geometry."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..models.board import Board
from .ses_net_resolver import RoutedSession

KI_CAD_COPPER_LAYERS = {"F.Cu", "B.Cu"}
SES_LAYER_MAP = {
    "TOP": "F.Cu",
    "BOTTOM": "B.Cu",
    "signal": "F.Cu",
    "F.Cu": "F.Cu",
    "B.Cu": "B.Cu",
}


@dataclass(frozen=True)
class RoutingValidationIssue:
    severity: str
    code: str
    message: str
    net_name: str | None = None


@dataclass
class RoutingValidationResult:
    ok: bool = True
    issues: list[RoutingValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[RoutingValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[RoutingValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]


def validate_routed_session(
    session: RoutedSession,
    board: Board,
    *,
    reject_unknown_nets: bool = True,
    reject_net_zero: bool = True,
    reject_unmapped_layers: bool = True,
) -> RoutingValidationResult:
    result = RoutingValidationResult()

    for segment in session.segments:
        _validate_net(result, segment.net_name, board, reject_unknown_nets, reject_net_zero)
        _validate_layer(result, segment.layer, segment.net_name, reject_unmapped_layers)
        if not _finite(segment.x1_mm, segment.y1_mm, segment.x2_mm, segment.y2_mm):
            _add(
                result,
                "error",
                "SES_IMPORT_INVALID_GEOMETRY",
                "segment has non-finite coordinates",
                segment.net_name,
            )
        if not math.isfinite(segment.width_mm) or segment.width_mm <= 0:
            _add(
                result,
                "error",
                "SES_IMPORT_INVALID_GEOMETRY",
                "segment width must be positive",
                segment.net_name,
            )

    for via in session.vias:
        _validate_net(result, via.net_name, board, reject_unknown_nets, reject_net_zero)
        if not _finite(via.x_mm, via.y_mm):
            _add(
                result,
                "error",
                "SES_IMPORT_INVALID_GEOMETRY",
                "via has non-finite coordinates",
                via.net_name,
            )
        for layer in via.layers:
            _validate_layer(result, layer, via.net_name, reject_unmapped_layers)
        if via.drill_mm is not None and via.drill_mm <= 0:
            _add(
                result,
                "error",
                "SES_IMPORT_INVALID_GEOMETRY",
                "via drill must be positive",
                via.net_name,
            )
        if via.diameter_mm is not None and via.diameter_mm <= 0:
            _add(
                result,
                "error",
                "SES_IMPORT_INVALID_GEOMETRY",
                "via diameter must be positive",
                via.net_name,
            )

    result.ok = not result.errors
    return result


def map_ses_layer(layer: str) -> str | None:
    if layer in SES_LAYER_MAP:
        return SES_LAYER_MAP[layer]
    if layer.startswith("In") and layer.endswith(".Cu"):
        return layer
    return None


def _validate_net(
    result: RoutingValidationResult,
    net_name: str,
    board: Board,
    reject_unknown_nets: bool,
    reject_net_zero: bool,
) -> None:
    if not net_name:
        _add(result, "error", "SES_IMPORT_MISSING_NET", "route has no net name", None)
        return
    if reject_net_zero and net_name == "0":
        _add(
            result,
            "error",
            "SES_IMPORT_NET_ZERO",
            "SES route explicitly targets net 0",
            net_name,
        )
        return
    net_id = board.nets.get(net_name)
    if reject_unknown_nets and net_id is None:
        _add(
            result,
            "error",
            "SES_IMPORT_UNKNOWN_NET",
            f"SES net is not present in KiCad board: {net_name}",
            net_name,
        )
        return
    if reject_net_zero and net_id == 0:
        _add(
            result,
            "error",
            "SES_IMPORT_NET_ZERO",
            f"SES route resolves to KiCad net 0: {net_name}",
            net_name,
        )


def _validate_layer(
    result: RoutingValidationResult,
    layer: str,
    net_name: str,
    reject_unmapped_layers: bool,
) -> None:
    mapped = map_ses_layer(layer)
    if mapped is None and reject_unmapped_layers:
        _add(
            result,
            "error",
            "SES_IMPORT_UNMAPPED_LAYER",
            f"SES layer is not recognized or mappable: {layer}",
            net_name,
        )


def _finite(*values: float) -> bool:
    return all(math.isfinite(value) for value in values)


def _add(
    result: RoutingValidationResult,
    severity: str,
    code: str,
    message: str,
    net_name: str | None,
) -> None:
    result.issues.append(
        RoutingValidationIssue(
            severity=severity,
            code=code,
            message=message,
            net_name=net_name,
        )
    )
