"""Tests for signal-aware placement scoring."""

import pytest

from ai_probe_router.models.board import Board, BoundingBox, Footprint, Pad
from ai_probe_router.models.net import NetRole, NetSubRole
from ai_probe_router.solvers.signal_aware_scoring import signal_score


def _make_board(footprints=None):
    board = Board(raw=[])
    board.footprints = footprints or []
    return board


def _make_footprint(ref, x, y, pads=None):
    fp = Footprint(ref=ref, lib_id="", x=x, y=y, layer="F.Cu", pads=pads or [])
    return fp


def _make_pad(net_name="", x=0.0, y=0.0):
    return Pad(
        number="1", pad_type="smd", shape="circle",
        x=x, y=y, width=1.0, height=1.0,
        net_name=net_name,
    )


class TestStrappingPinScore:
    def test_near_ic_penalized(self):
        board = _make_board([_make_footprint("U1", 50.0, 50.0)])
        score, warnings = signal_score(
            51.0, 50.0, NetRole.GPIO, {NetSubRole.STRAPPING_PIN}, board,
        )
        assert score < 0
        assert len(warnings) >= 1
        assert "strapping" in warnings[0].lower() or "boot" in warnings[0].lower()

    def test_far_from_ic_rewarded(self):
        board = _make_board([_make_footprint("U1", 50.0, 50.0)])
        score, _ = signal_score(
            70.0, 50.0, NetRole.GPIO, {NetSubRole.STRAPPING_PIN}, board,
        )
        assert score > 0

    def test_no_ic_no_effect(self):
        board = _make_board([_make_footprint("R1", 50.0, 50.0)])
        score, _ = signal_score(
            51.0, 50.0, NetRole.GPIO, {NetSubRole.STRAPPING_PIN}, board,
        )
        assert score == 0.0


class TestAdcScore:
    def test_near_clock_penalized(self):
        clock_pad = _make_pad(net_name="CLK_48M", x=0.0, y=0.0)
        board = _make_board([_make_footprint("U1", 50.0, 50.0, [clock_pad])])
        score, warnings = signal_score(
            51.0, 50.0, NetRole.ANALOG, {NetSubRole.ADC_INPUT}, board,
        )
        assert score < 0
        assert any("noise" in w.lower() or "clock" in w.lower() for w in warnings)

    def test_far_from_clock_ok(self):
        clock_pad = _make_pad(net_name="CLK_48M", x=0.0, y=0.0)
        board = _make_board([_make_footprint("U1", 50.0, 50.0, [clock_pad])])
        score, warnings = signal_score(
            70.0, 70.0, NetRole.ANALOG, {NetSubRole.ADC_INPUT}, board,
        )
        assert score >= 0

    def test_no_clock_nets_neutral(self):
        board = _make_board([_make_footprint("U1", 50.0, 50.0)])
        score, _ = signal_score(
            51.0, 50.0, NetRole.ANALOG, {NetSubRole.ADC_INPUT}, board,
        )
        assert score == 0.0


class TestPowerScore:
    def test_near_ic_boosted(self):
        board = _make_board([_make_footprint("U1", 50.0, 50.0)])
        score, _ = signal_score(
            52.0, 50.0, NetRole.POWER, set(), board,
        )
        assert score > 0

    def test_far_from_ic_neutral(self):
        board = _make_board([_make_footprint("U1", 50.0, 50.0)])
        score, _ = signal_score(
            80.0, 80.0, NetRole.POWER, set(), board,
        )
        assert score == 0.0


class TestAudioScore:
    def test_near_clock_penalized(self):
        clock_pad = _make_pad(net_name="XTAL_OUT", x=0.0, y=0.0)
        board = _make_board([_make_footprint("Y1", 50.0, 50.0, [clock_pad])])
        score, warnings = signal_score(
            51.0, 50.0, NetRole.ANALOG, {NetSubRole.AUDIO_ANALOG}, board,
        )
        assert score < 0
        assert any("audio" in w.lower() or "crosstalk" in w.lower() for w in warnings)


class TestBatteryWarning:
    def test_battery_subrole_warns(self):
        board = _make_board()
        _, warnings = signal_score(
            10.0, 10.0, NetRole.POWER, {NetSubRole.BATTERY}, board,
        )
        assert any("battery" in w.lower() or "protection" in w.lower() for w in warnings)


class TestNoSubRoles:
    def test_plain_gpio_no_signal_adjustment(self):
        board = _make_board([_make_footprint("U1", 50.0, 50.0)])
        score, warnings = signal_score(
            52.0, 50.0, NetRole.GPIO, set(), board,
        )
        assert score == 0.0
        assert len(warnings) == 0
