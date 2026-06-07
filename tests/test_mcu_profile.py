"""Tests for MCU profile loading and queries."""

from pathlib import Path

import pytest

from ai_probe_router.models.mcu_profile import (
    AdcChannel,
    McuProfile,
    StrappingPin,
    load_mcu_profile,
)


@pytest.fixture()
def esp32s3_profile() -> McuProfile:
    yaml_path = Path(__file__).parent.parent / "libraries" / "mcu_profiles" / "esp32_s3.yaml"
    return load_mcu_profile(yaml_path)


def test_load_esp32s3_basic(esp32s3_profile: McuProfile):
    assert esp32s3_profile.name == "esp32-s3"
    assert esp32s3_profile.family == "espressif"


def test_strapping_pins(esp32s3_profile: McuProfile):
    assert esp32s3_profile.is_strapping_pin("GPIO0")
    assert esp32s3_profile.is_strapping_pin("GPIO3")
    assert esp32s3_profile.is_strapping_pin("GPIO45")
    assert esp32s3_profile.is_strapping_pin("GPIO46")
    assert not esp32s3_profile.is_strapping_pin("GPIO1")
    assert not esp32s3_profile.is_strapping_pin("GPIO10")


def test_strapping_info(esp32s3_profile: McuProfile):
    info = esp32s3_profile.get_strapping_info("GPIO0")
    assert info is not None
    assert info.function == "Boot mode select"
    assert info.default_state == "pull-up"

    info45 = esp32s3_profile.get_strapping_info("GPIO45")
    assert info45 is not None
    assert info45.default_state == "pull-down"

    assert esp32s3_profile.get_strapping_info("GPIO99") is None


def test_adc_capable(esp32s3_profile: McuProfile):
    for i in range(1, 21):
        assert esp32s3_profile.is_adc_capable(f"GPIO{i}"), f"GPIO{i} should be ADC-capable"
    assert not esp32s3_profile.is_adc_capable("GPIO0")
    assert not esp32s3_profile.is_adc_capable("GPIO21")
    assert not esp32s3_profile.is_adc_capable("GPIO39")
    assert not esp32s3_profile.is_adc_capable("GPIO48")


def test_adc_channels_count(esp32s3_profile: McuProfile):
    assert len(esp32s3_profile.adc_channels) == 20
    adc1 = [ch for ch in esp32s3_profile.adc_channels if ch.adc_unit == 1]
    adc2 = [ch for ch in esp32s3_profile.adc_channels if ch.adc_unit == 2]
    assert len(adc1) == 10
    assert len(adc2) == 10


def test_reserved_gpios(esp32s3_profile: McuProfile):
    for i in range(26, 33):
        assert esp32s3_profile.is_reserved(f"GPIO{i}")
    assert not esp32s3_profile.is_reserved("GPIO1")
    assert not esp32s3_profile.is_reserved("GPIO25")


def test_case_insensitive(esp32s3_profile: McuProfile):
    assert esp32s3_profile.is_adc_capable("gpio1")
    assert esp32s3_profile.is_strapping_pin("gpio0")
    assert esp32s3_profile.is_reserved("gpio26")


def test_notes(esp32s3_profile: McuProfile):
    assert len(esp32s3_profile.notes) >= 2


def test_inline_profile():
    profile = McuProfile(
        name="test-mcu",
        family="test",
        strapping_pins=[StrappingPin(gpio="GPIO0", function="boot")],
        adc_channels=[AdcChannel(gpio="GPIO1", adc_unit=1, channel=0)],
    )
    assert profile.is_strapping_pin("GPIO0")
    assert profile.is_adc_capable("GPIO1")
    assert not profile.is_adc_capable("GPIO2")
