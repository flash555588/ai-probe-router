"""Tests for net-aware SES route parsing."""

from __future__ import annotations

import pytest

from ai_probe_router.routing.ses_net_resolver import (
    SesNetResolutionError,
    parse_ses_routes_text,
)


def test_parses_single_net_with_one_wire():
    session = parse_ses_routes_text("""(session "test"
  (route
    (net "SWDIO"
      (wire (path TOP 150 10000 10000 20000 10000))
    )
  )
)""")

    assert len(session.segments) == 1
    segment = session.segments[0]
    assert segment.net_name == "SWDIO"
    assert segment.layer == "TOP"
    assert segment.x1_mm == 10.0
    assert segment.x2_mm == 20.0
    assert segment.width_mm == 0.15


def test_parses_one_net_with_multiple_wires():
    session = parse_ses_routes_text("""(session "test"
  (route
    (net "SIG"
      (wire
        (path TOP 150 0 0 10000 0 20000 0)
      )
    )
  )
)""")

    assert [segment.net_name for segment in session.segments] == ["SIG", "SIG"]


def test_parses_multiple_nets():
    session = parse_ses_routes_text("""(session "test"
  (route
    (net "GND" (wire (path TOP 150 0 0 10000 0)))
    (net "SWCLK" (wire (path BOTTOM 150 0 1000 10000 1000)))
  )
)""")

    assert [segment.net_name for segment in session.segments] == ["GND", "SWCLK"]


def test_parses_vias_inside_net_context():
    session = parse_ses_routes_text("""(session "test"
  (route
    (net "SIG"
      (via (via_via TOP BOTTOM) (xy 30000 40000))
    )
  )
)""")

    assert len(session.vias) == 1
    via = session.vias[0]
    assert via.net_name == "SIG"
    assert via.layers == ("TOP", "BOTTOM")
    assert via.x_mm == 30.0
    assert via.y_mm == 40.0


def test_rejects_wire_outside_net_context():
    with pytest.raises(SesNetResolutionError, match="wire outside net block"):
        parse_ses_routes_text("""(session "test"
  (route
    (wire (path TOP 150 0 0 10000 0))
  )
)""")


def test_rejects_missing_net_name():
    with pytest.raises(SesNetResolutionError, match="missing net name"):
        parse_ses_routes_text("""(session "test" (route (net)))""")


def test_preserves_quoted_net_names_with_symbols():
    session = parse_ses_routes_text("""(session "test"
  (route
    (net "ADC/SIG-1_A"
      (wire (path TOP 150 0 0 10000 0))
    )
  )
)""")

    assert session.segments[0].net_name == "ADC/SIG-1_A"
