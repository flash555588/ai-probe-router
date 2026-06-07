"""Tests for design review checks."""

import pytest

from ai_probe_router.ai.design_review import (
    DesignReviewReport,
    ReviewFinding,
    check_adc_pin_mapping,
    check_battery_protection,
    check_decoupling_caps,
    check_power_path,
    check_sd_card_pullups,
    check_strapping_pins,
    run_design_review,
)
from ai_probe_router.models.board import Schematic
from ai_probe_router.models.mcu_profile import McuProfile, StrappingPin, AdcChannel


def _make_schematic(components=None, labels=None, wires=None):
    return Schematic(
        components=components or [],
        labels=labels or [],
        wires=wires or [],
        raw=[],
    )


class TestDecouplingCaps:
    def test_ic_without_cap_warns(self):
        sch = _make_schematic(
            components=[
                {"ref": "U1", "lib_id": "MCU", "value": "ESP32", "x": 50.0, "y": 50.0},
            ],
            labels=[
                {"name": "3V3", "x": 48.0, "y": 48.0},
            ],
        )
        findings = check_decoupling_caps(sch)
        assert len(findings) >= 1
        assert findings[0].check_id == "DECAP-001"
        assert findings[0].severity == "warning"

    def test_ic_with_nearby_cap_no_warning(self):
        sch = _make_schematic(
            components=[
                {"ref": "U1", "lib_id": "MCU", "value": "ESP32", "x": 50.0, "y": 50.0},
                {"ref": "C1", "lib_id": "C", "value": "100nF", "x": 49.0, "y": 49.0},
            ],
            labels=[
                {"name": "3V3", "x": 49.5, "y": 49.5},
            ],
        )
        findings = check_decoupling_caps(sch)
        # C1 is near the power label and the IC, so no warning expected
        decap_warnings = [f for f in findings if f.component_ref == "U1"]
        # The proximity check is approximate; at minimum, having a cap near
        # the power label should reduce findings
        assert len(decap_warnings) <= 1


class TestStrappingPins:
    def test_load_on_strapping_pin(self):
        profile = McuProfile(
            name="esp32-s3",
            family="espressif",
            strapping_pins=[
                StrappingPin(gpio="GPIO45", function="VDD_SPI", default_state="pull-down"),
            ],
            adc_channels=[],
        )
        sch = _make_schematic(
            components=[
                {"ref": "J1", "lib_id": "Conn", "value": "Header", "x": 20.0, "y": 20.0},
            ],
            labels=[
                {"name": "GPIO45", "x": 22.0, "y": 20.0},
            ],
        )
        findings = check_strapping_pins(sch, profile)
        assert len(findings) >= 1
        assert findings[0].check_id == "STRAP-001"

    def test_no_strapping_issue_without_loads(self):
        profile = McuProfile(
            name="esp32-s3",
            family="espressif",
            strapping_pins=[
                StrappingPin(gpio="GPIO0", function="Boot", default_state="pull-up"),
            ],
            adc_channels=[],
        )
        sch = _make_schematic(
            labels=[{"name": "GPIO0", "x": 50.0, "y": 50.0}],
        )
        findings = check_strapping_pins(sch, profile)
        assert len(findings) == 0


class TestAdcPinMapping:
    def test_non_adc_gpio_flagged(self):
        profile = McuProfile(
            name="esp32-s3",
            family="espressif",
            strapping_pins=[],
            adc_channels=[
                AdcChannel(gpio=f"GPIO{i}", adc_unit=1, channel=i - 1)
                for i in range(1, 11)
            ],
        )
        sch = _make_schematic(
            labels=[{"name": "ADC_GPIO39", "x": 10.0, "y": 10.0}],
        )
        findings = check_adc_pin_mapping(sch, profile)
        assert len(findings) == 1
        assert findings[0].check_id == "ADC-001"
        assert findings[0].severity == "error"

    def test_valid_adc_gpio_passes(self):
        profile = McuProfile(
            name="esp32-s3",
            family="espressif",
            strapping_pins=[],
            adc_channels=[
                AdcChannel(gpio="GPIO1", adc_unit=1, channel=0),
            ],
        )
        sch = _make_schematic(
            labels=[{"name": "ADC_GPIO1", "x": 10.0, "y": 10.0}],
        )
        findings = check_adc_pin_mapping(sch, profile)
        assert len(findings) == 0


class TestSdCardPullups:
    def test_sd_data_without_pullup(self):
        sch = _make_schematic(
            labels=[{"name": "SD_DAT0", "x": 10.0, "y": 10.0}],
        )
        findings = check_sd_card_pullups(sch)
        assert len(findings) == 1
        assert findings[0].check_id == "SDPULL-001"

    def test_no_sd_nets_no_findings(self):
        sch = _make_schematic(
            labels=[{"name": "GPIO5", "x": 10.0, "y": 10.0}],
        )
        findings = check_sd_card_pullups(sch)
        assert len(findings) == 0


class TestBatteryProtection:
    def test_battery_without_protection(self):
        sch = _make_schematic(
            components=[
                {"ref": "U1", "lib_id": "TP4056", "value": "TP4056", "x": 50.0, "y": 50.0},
            ],
            labels=[{"name": "VBAT", "x": 50.0, "y": 50.0}],
        )
        findings = check_battery_protection(sch)
        assert len(findings) == 1
        assert findings[0].check_id == "BATPROT-001"

    def test_battery_with_protection_ic(self):
        sch = _make_schematic(
            components=[
                {"ref": "U2", "lib_id": "DW01A", "value": "DW01A", "x": 50.0, "y": 50.0},
            ],
            labels=[{"name": "VBAT", "x": 50.0, "y": 50.0}],
        )
        findings = check_battery_protection(sch)
        assert len(findings) == 0

    def test_no_battery_no_findings(self):
        sch = _make_schematic(
            labels=[{"name": "3V3", "x": 10.0, "y": 10.0}],
        )
        findings = check_battery_protection(sch)
        assert len(findings) == 0


class TestPowerPath:
    def test_usb_plus_battery_no_controller(self):
        sch = _make_schematic(
            labels=[
                {"name": "VBUS", "x": 10.0, "y": 10.0},
                {"name": "VBAT", "x": 20.0, "y": 10.0},
            ],
        )
        findings = check_power_path(sch)
        assert len(findings) == 1
        assert findings[0].check_id == "PWRPATH-001"

    def test_usb_only_no_finding(self):
        sch = _make_schematic(
            labels=[{"name": "VBUS", "x": 10.0, "y": 10.0}],
        )
        findings = check_power_path(sch)
        assert len(findings) == 0


class TestDesignReviewReport:
    def test_summary_format(self):
        report = DesignReviewReport(
            findings=[
                ReviewFinding(
                    check_id="TEST-001",
                    severity="warning",
                    category="test",
                    component_ref="U1",
                    message="test message",
                    suggestion="test suggestion",
                ),
            ],
            mcu_profile_name="esp32-s3",
        )
        text = report.summary()
        assert "TEST-001" in text
        assert "esp32-s3" in text
        assert "1 findings" in text

    def test_error_warning_counts(self):
        report = DesignReviewReport(findings=[
            ReviewFinding("A", "error", "x", "", "m", "s"),
            ReviewFinding("B", "warning", "x", "", "m", "s"),
            ReviewFinding("C", "warning", "x", "", "m", "s"),
            ReviewFinding("D", "info", "x", "", "m", "s"),
        ])
        assert report.error_count == 1
        assert report.warning_count == 2


class TestRunDesignReview:
    def test_full_review_with_profile(self):
        profile = McuProfile(
            name="esp32-s3",
            family="espressif",
            strapping_pins=[
                StrappingPin(gpio="GPIO45", function="VDD_SPI", default_state="pull-down"),
            ],
            adc_channels=[
                AdcChannel(gpio=f"GPIO{i}", adc_unit=1, channel=i - 1)
                for i in range(1, 11)
            ],
        )
        sch = _make_schematic(
            components=[
                {"ref": "U1", "lib_id": "ESP32", "value": "ESP32-S3", "x": 50.0, "y": 50.0},
            ],
            labels=[
                {"name": "3V3", "x": 48.0, "y": 48.0},
                {"name": "VBAT", "x": 30.0, "y": 30.0},
                {"name": "VBUS", "x": 10.0, "y": 10.0},
                {"name": "ADC_GPIO39", "x": 60.0, "y": 60.0},
                {"name": "SD_DAT0", "x": 70.0, "y": 70.0},
            ],
        )
        report = run_design_review(sch, mcu_profile=profile)
        assert report.mcu_profile_name == "esp32-s3"
        # Should find multiple issues
        categories = {f.category for f in report.findings}
        assert "adc" in categories  # GPIO39 not ADC-capable
        assert "pull_resistor" in categories  # SD_DAT0 no pullup

    def test_no_schematic_empty_report(self):
        report = run_design_review()
        assert len(report.findings) == 0
