"""Transactional route-import safety tests."""

from __future__ import annotations

import json

from ai_probe_router.routing.route_import_transaction import import_ses_transactional
from ai_probe_router.routing.routing_validation import validate_routed_session
from ai_probe_router.routing.ses_net_resolver import RoutedSegment, RoutedSession
from ai_probe_router.verification.readiness_report import generate_readiness_report
from ai_probe_router.verification.report import CoverageReport


def test_unknown_ses_net_blocks_import_and_preserves_source(tmp_path):
    pcb_path = _write_board(tmp_path)
    original = pcb_path.read_text(encoding="utf-8")
    ses_path = _write_ses(tmp_path, "UNKNOWN", layer="TOP")

    result = import_ses_transactional(pcb_path, ses_path, tmp_path / "output")

    assert not result.ok
    assert result.errors[0].code == "SES_IMPORT_UNKNOWN_NET"
    assert pcb_path.read_text(encoding="utf-8") == original
    assert (tmp_path / "output" / "main.routed.candidate.kicad_pcb").exists()
    assert not (tmp_path / "output" / "main.routed.kicad_pcb").exists()


def test_net_zero_import_is_rejected(tmp_path):
    pcb_path = _write_board(tmp_path)
    ses_path = _write_ses(tmp_path, "0", layer="TOP")

    result = import_ses_transactional(pcb_path, ses_path, tmp_path / "output")

    assert not result.ok
    assert result.errors[0].code == "SES_IMPORT_NET_ZERO"


def test_invalid_layer_blocks_import(tmp_path):
    pcb_path = _write_board(tmp_path)
    ses_path = _write_ses(tmp_path, "GND", layer="INNER_UNKNOWN")

    result = import_ses_transactional(pcb_path, ses_path, tmp_path / "output")

    assert not result.ok
    assert result.errors[0].code == "SES_IMPORT_UNMAPPED_LAYER"


def test_invalid_coordinate_blocks_import(tmp_path):
    pcb_path = _write_board(tmp_path)
    ses_path = _write_ses(tmp_path, "GND", layer="TOP", x1="NaN")

    result = import_ses_transactional(pcb_path, ses_path, tmp_path / "output")

    assert not result.ok
    assert result.errors[0].code == "SES_IMPORT_INVALID_GEOMETRY"


def test_valid_import_promotes_final_board_with_resolved_net(tmp_path):
    pcb_path = _write_board(tmp_path)
    ses_path = _write_ses(tmp_path, "GND", layer="TOP")

    result = import_ses_transactional(pcb_path, ses_path, tmp_path / "output")

    assert result.ok
    final = tmp_path / "output" / "main.routed.kicad_pcb"
    assert final.exists()
    text = final.read_text(encoding="utf-8")
    assert "(net 1)" in text
    assert "(net 0)" not in text


def test_readiness_json_blocks_route_import_errors(tmp_path):
    session = RoutedSession(
        segments=[
            RoutedSegment("UNKNOWN", "TOP", 0.0, 0.0, 1.0, 1.0, 0.15),
        ],
    )
    validation = validate_routed_session(session, _board_model())

    report = generate_readiness_report(
        CoverageReport(run_id="APR-ROUTE"),
        route_import_validation=validation,
    )
    path = tmp_path / "readiness_report.json"
    report.write_json(path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["verdict"] == "BLOCKED"
    assert payload["exit_code"] == 3
    assert payload["issues"][0]["source"] == "route_import"


def _write_board(tmp_path):
    path = tmp_path / "main.kicad_pcb"
    path.write_text(_board_text(), encoding="utf-8")
    return path


def _write_ses(tmp_path, net_name: str, *, layer: str, x1: str = "0"):
    path = tmp_path / f"{net_name.replace('/', '_')}_{layer}.ses"
    path.write_text(f"""(session "test"
  (route
    (net "{net_name}"
      (wire (path {layer} 150 {x1} 0 10000 0))
    )
  )
)""", encoding="utf-8")
    return path


def _board_model():
    import tempfile
    from pathlib import Path

    from ai_probe_router.eda_adapters.kicad.pcb_parser import parse_pcb

    root = Path(tempfile.mkdtemp(prefix="apr-route-test-"))
    path = root / "main.kicad_pcb"
    path.write_text(_board_text(), encoding="utf-8")
    return parse_pcb(path)


def _board_text() -> str:
    return """(kicad_pcb
  (version 20240108)
  (general (thickness 1.6))
  (paper "A4")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (44 "Edge.Cuts" user))
  (net 0 "")
  (net 1 "GND")
  (net 2 "SIG")
  (gr_rect (start 0 0) (end 50 50)
    (stroke (width 0.1) (type default))
    (fill none) (layer "Edge.Cuts") (uuid "edge"))
)"""
