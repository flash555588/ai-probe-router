from ai_probe_router.models.module import FunctionalModule
from ai_probe_router.solvers.module_selector import select_modules
from ai_probe_router.verification.module_report import ModuleReport


def test_module_selector_picks_matching_gpio_expander():
    module = FunctionalModule(
        name="scalable_gpio",
        type="gpio_expansion",
        channels=16,
        allowed_interfaces=["i2c", "spi"],
        require_level_shift=True,
        require_esd=True,
    )

    result = select_modules([module])

    assert result.ok
    assert len(result.selected) == 1
    selected = result.selected[0]
    assert selected.implementation.name == "i2c_gpio_expander_16_level_shifted"
    assert "interfaces: i2c" in selected.reasons


def test_module_selector_reports_incompatible_requirement():
    module = FunctionalModule(
        name="too_many_gpio",
        type="gpio_expansion",
        channels=64,
        allowed_interfaces=["i2c"],
        required=True,
    )

    result = select_modules([module])

    assert not result.ok
    assert "No valid implementation" in result.errors[0]


def test_module_report_lists_selection_and_rejections():
    module = FunctionalModule(
        name="power_observation",
        type="current_voltage_monitor",
        telemetry_bus="i2c",
        rails=["VDD_3V3", "VBUS_5V"],
    )
    result = select_modules([module])
    text = ModuleReport(result).summary_text()

    assert "Module Planning Report" in text
    assert "power_observation" in text
    assert "i2c_current_monitor_with_sense_resistor" in text

