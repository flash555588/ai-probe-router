"""Tests for net sub-role classification."""


from ai_probe_router.ai.net_classifier import classify_net_detailed
from ai_probe_router.models.mcu_profile import McuProfile, StrappingPin
from ai_probe_router.models.net import NetRole, NetSubRole


def test_i2s_data_nets():
    for name in ("I2S_DIN", "I2S_DOUT", "I2S_SD", "I2S_DATA"):
        _, subs = classify_net_detailed(name)
        assert NetSubRole.I2S_DATA in subs, f"{name} should be I2S_DATA"


def test_i2s_clock_nets():
    for name in ("BCLK", "LRCK", "I2S_CLK", "I2S_SCK", "MCLK", "WS"):
        _, subs = classify_net_detailed(name)
        assert NetSubRole.I2S_CLOCK in subs, f"{name} should be I2S_CLOCK"


def test_sd_data_nets():
    for name in ("SD_DAT0", "SD_CMD", "SD_D1", "SDIO_D0", "SDIO_CMD"):
        _, subs = classify_net_detailed(name)
        assert NetSubRole.SD_DATA in subs, f"{name} should be SD_DATA"


def test_sd_clock_nets():
    for name in ("SD_CLK", "SDIO_CLK"):
        _, subs = classify_net_detailed(name)
        assert NetSubRole.SD_CLK in subs, f"{name} should be SD_CLK"


def test_battery_nets():
    for name in ("VBAT", "BAT+", "BATTERY", "LI_ION"):
        _, subs = classify_net_detailed(name)
        assert NetSubRole.BATTERY in subs, f"{name} should be BATTERY"


def test_audio_analog_nets():
    for name in ("AUDIO_OUT", "HP_L", "HP_R", "OUTL", "OUTR", "LINE_OUT", "MIC_IN", "SPK"):
        _, subs = classify_net_detailed(name)
        assert NetSubRole.AUDIO_ANALOG in subs, f"{name} should be AUDIO_ANALOG"


def test_adc_input_nets():
    for name in ("ADC_CH0", "AIN1", "AN3"):
        _, subs = classify_net_detailed(name)
        assert NetSubRole.ADC_INPUT in subs, f"{name} should be ADC_INPUT"


def test_usb_data_nets():
    for name in ("USB_DP", "USB_DM", "D+", "D-"):
        _, subs = classify_net_detailed(name)
        assert NetSubRole.USB_DATA in subs, f"{name} should be USB_DATA"


def test_analog_ground():
    for name in ("AGND", "GNDA", "GND_A"):
        _, subs = classify_net_detailed(name)
        assert NetSubRole.ANALOG_GROUND in subs, f"{name} should be ANALOG_GROUND"


def test_no_sub_roles_for_plain_gpio():
    _, subs = classify_net_detailed("GPIO15")
    # GPIO15 should not have any sub-roles from pattern matching alone
    assert NetSubRole.STRAPPING_PIN not in subs


def test_strapping_pin_with_mcu_profile():
    profile = McuProfile(
        name="test",
        family="test",
        strapping_pins=[
            StrappingPin(gpio="GPIO0", function="boot"),
            StrappingPin(gpio="GPIO45", function="vdd_spi"),
        ],
        adc_channels=[],
    )
    _, subs = classify_net_detailed("GPIO0", mcu_profile=profile)
    assert NetSubRole.STRAPPING_PIN in subs

    _, subs2 = classify_net_detailed("IO0", mcu_profile=profile)
    assert NetSubRole.STRAPPING_PIN in subs2

    _, subs3 = classify_net_detailed("GPIO45_CTRL", mcu_profile=profile)
    assert NetSubRole.STRAPPING_PIN in subs3


def test_non_strapping_with_profile():
    profile = McuProfile(
        name="test",
        family="test",
        strapping_pins=[StrappingPin(gpio="GPIO0", function="boot")],
        adc_channels=[],
    )
    _, subs = classify_net_detailed("GPIO10", mcu_profile=profile)
    assert NetSubRole.STRAPPING_PIN not in subs


def test_role_unchanged_by_sub_roles():
    role, _ = classify_net_detailed("VBAT")
    assert role == NetRole.POWER

    role2, _ = classify_net_detailed("SD_CLK")
    assert role2 == NetRole.CLOCK  # CLK pattern matches CLOCK role


def test_multiple_sub_roles():
    # A net can match multiple sub-role patterns
    _, subs = classify_net_detailed("ADC_AUDIO_IN")
    assert NetSubRole.ADC_INPUT in subs
    assert NetSubRole.AUDIO_ANALOG in subs
