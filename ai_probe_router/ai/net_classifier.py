"""Rule-based net classification (Phase 1 — no LLM dependency)."""

from __future__ import annotations

import re

from ..models.net import NetRole

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


def classify_net(name: str) -> NetRole:
    for pattern, role in _PATTERNS:
        if pattern.search(name):
            return role
    return NetRole.UNKNOWN


def classify_nets(names: list[str]) -> dict[str, NetRole]:
    return {n: classify_net(n) for n in names}
