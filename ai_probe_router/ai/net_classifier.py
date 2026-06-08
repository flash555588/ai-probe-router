"""Rule-based net classification (Phase 1 — no LLM dependency)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..models.net import NetRole, NetSubRole

if TYPE_CHECKING:
    from ..models.mcu_profile import McuProfile

_PATTERNS: list[tuple[re.Pattern, NetRole]] = [
    (re.compile(r"^(GND|AGND|PGND|DGND|VSS|GNDA)$", re.I), NetRole.GROUND),
    (re.compile(r"^(VCC|VDD|VBUS|VIN|V\d|3V3|5V|1V8|12V|VBAT|\+\d).*", re.I), NetRole.POWER),
    (re.compile(r"(SWDIO|SWCLK|SWD|JTAG|TDI|TDO|TMS|TCK|TRST)", re.I), NetRole.DEBUG),
    (re.compile(r"(NRST|RESET|RST|BOOT\d?)", re.I), NetRole.RESET),
    (re.compile(r"(UART|USART|TX|RX|TXD|RXD)", re.I), NetRole.COMMUNICATION),
    (re.compile(r"(SPI|MOSI|MISO|SCK|SCLK|CS|NSS)", re.I), NetRole.COMMUNICATION),
    (re.compile(r"(I2C|SDA|SCL|TWI)", re.I), NetRole.COMMUNICATION),
    (re.compile(r"(CAN|CANH|CANL|CAN_TX|CAN_RX)", re.I), NetRole.COMMUNICATION),
    (re.compile(r"(USB|D\+|D-|USB_DP|USB_DM|USB_VBUS)", re.I), NetRole.HIGH_SPEED),
    (re.compile(r"(ETH|RMII|MII|MDIO|MDC)", re.I), NetRole.HIGH_SPEED),
    (re.compile(r"(CLK|CLOCK|XTAL|OSC|HSE|LSE)", re.I), NetRole.CLOCK),
    (re.compile(r"(ADC|AIN|ANALOG|VREF|AREF|AN\d)", re.I), NetRole.ANALOG),
    (re.compile(r"(GPIO|PA\d|PB\d|PC\d|PD\d|PE\d|PF\d|PG\d|PH\d|IO\d)", re.I), NetRole.GPIO),
]

_SUB_PATTERNS: list[tuple[re.Pattern, NetSubRole]] = [
    # Audio I2S
    (re.compile(r"(I2S_?D|I2S_?SD|DIN|DOUT|I2S_?DATA)", re.I), NetSubRole.I2S_DATA),
    (
        re.compile(r"(BCLK|BIT_?CLK|I2S_?CLK|LRCK|WS|WORD_?SEL|MCLK|I2S_?SCK)", re.I),
        NetSubRole.I2S_CLOCK,
    ),
    # SD card
    (re.compile(r"(SD_?DAT|SD_?D\d|SD_?CMD|SDIO_?D|SDIO_?CMD)", re.I), NetSubRole.SD_DATA),
    (re.compile(r"(SD_?CLK|SDIO_?CLK)", re.I), NetSubRole.SD_CLK),
    # Battery
    (re.compile(r"(VBAT|BAT_?\+|BATTERY|LI_?ION|CELL)", re.I), NetSubRole.BATTERY),
    # Audio analog
    (
        re.compile(r"(AUDIO|HP_?L|HP_?R|OUTL|OUTR|LINE_?OUT|MIC_?IN|SPK)", re.I),
        NetSubRole.AUDIO_ANALOG,
    ),
    # ADC
    (re.compile(r"(ADC|AIN|AN\d|VREF|AREF)", re.I), NetSubRole.ADC_INPUT),
    # USB
    (re.compile(r"(USB_?D[PM]|USB_?DP|USB_?DM|D\+|D-)", re.I), NetSubRole.USB_DATA),
    # Analog ground
    (re.compile(r"^(AGND|GNDA|GND_?A)$", re.I), NetSubRole.ANALOG_GROUND),
]


def classify_net(name: str) -> NetRole:
    for pattern, role in _PATTERNS:
        if pattern.search(name):
            return role
    return NetRole.UNKNOWN


def classify_net_detailed(
    name: str,
    mcu_profile: McuProfile | None = None,
) -> tuple[NetRole, set[NetSubRole]]:
    role = classify_net(name)
    sub_roles: set[NetSubRole] = set()

    for pattern, sub_role in _SUB_PATTERNS:
        if pattern.search(name):
            sub_roles.add(sub_role)

    if mcu_profile:
        gpio_match = re.search(r"(GPIO\d+|IO\d+)", name, re.I)
        if gpio_match:
            gpio_name = gpio_match.group(1).upper()
            if not gpio_name.startswith("GPIO"):
                gpio_name = "GPIO" + gpio_name[2:]
            if mcu_profile.is_strapping_pin(gpio_name):
                sub_roles.add(NetSubRole.STRAPPING_PIN)

    return role, sub_roles


def classify_nets(names: list[str]) -> dict[str, NetRole]:
    return {n: classify_net(n) for n in names}


def classify_nets_detailed(
    names: list[str],
    mcu_profile: McuProfile | None = None,
) -> dict[str, tuple[NetRole, set[NetSubRole]]]:
    return {n: classify_net_detailed(n, mcu_profile) for n in names}
