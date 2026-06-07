from ai_probe_router.config import ProjectConfig
from ai_probe_router.models.design_graph import DesignGoals, HardwarePlatform
from ai_probe_router.models.module import FunctionalModule, parse_ai_hint
from ai_probe_router.models.power_domain import PowerDomain
from ai_probe_router.solvers.module_graph import build_module_graph
from ai_probe_router.solvers.module_selector import select_modules


def _build(modules, *, domains=None, max_area=0.0):
    cfg = ProjectConfig(
        schema_version=2,
        functional_modules=modules,
        hardware_platform=HardwarePlatform(target_voltage_domains=domains or []),
        design_goals=DesignGoals(max_added_area_mm2=max_area),
    )
    selection = select_modules(modules)
    return build_module_graph(cfg, selection)


def test_required_dependency_satisfied():
    result = _build([
        FunctionalModule(name="debug", type="debug_swd"),
        FunctionalModule(name="fixture", type="protected_probe_fixture", depends_on=["debug"]),
    ])

    assert result.ok
    assert any(dep.reason == "depends_on" for dep in result.graph.dependencies)
    assert result.graph.instances[0].instance_id == "MOD1"


def test_required_dependency_missing_fails():
    result = _build([
        FunctionalModule(name="fixture", type="protected_probe_fixture", depends_on=["debug"]),
    ])

    assert not result.ok
    assert "depends on missing module" in result.errors[0]


def test_optional_dependency_missing_warns():
    result = _build([
        FunctionalModule(
            name="fixture",
            type="protected_probe_fixture",
            required=False,
            depends_on=["debug"],
        ),
    ])

    assert result.ok
    assert "depends on missing module" in result.warnings[0]


def test_dependency_cycle_reports_error():
    result = _build([
        FunctionalModule(name="a", type="debug_swd", depends_on=["b"]),
        FunctionalModule(name="b", type="protected_probe_fixture", depends_on=["a"]),
    ])

    assert not result.ok
    assert any("cycle" in error.lower() for error in result.errors)


def test_generated_nets_are_deterministic():
    result = _build([
        FunctionalModule(name="debug", type="debug_swd", target_nets=["SWDIO", "SWCLK"]),
    ])
    instance = result.graph.instances[0]

    assert instance.instance_id == "MOD1"
    assert instance.generated_nets == [
        "MOD1_DEBUG_SWDIO",
        "MOD1_DEBUG_SWCLK",
    ]


def test_missing_voltage_domain_fails_required_module():
    result = _build([
        FunctionalModule(
            name="gpio",
            type="gpio_expansion",
            voltage_domains=["VDD_1V8"],
        ),
    ], domains=[PowerDomain(name="VDD_3V3", voltage=3.3)])

    assert not result.ok
    assert "missing voltage domain" in result.errors[0]


def test_i2c_address_conflict_is_reported():
    result = _build([
        FunctionalModule(name="analog_a", type="analog_measurement", telemetry_bus="i2c"),
        FunctionalModule(name="analog_b", type="analog_measurement", telemetry_bus="i2c"),
    ])

    assert not result.ok
    assert any("I2C address conflict" in error for error in result.errors)


def test_area_budget_overflow_is_reported():
    result = _build([
        FunctionalModule(name="analog", type="analog_measurement", budget_area_mm2=10),
    ])

    assert not result.ok
    assert "exceeds budget" in result.errors[0]


def test_duplicate_reserved_target_net_is_reported():
    result = _build([
        FunctionalModule(name="debug", type="debug_swd", target_nets=["SWDIO"]),
        FunctionalModule(name="fixture", type="protected_probe_fixture", target_nets=["SWDIO"]),
    ])

    assert not result.ok
    assert "reserved by multiple modules" in result.errors[0]


def test_unsupported_ai_hint_is_ignored():
    result = _build([
        FunctionalModule(
            name="analog",
            type="analog_measurement",
            ai_hints=[parse_ai_hint({"type": "magic_layout"})],
        ),
    ])

    assert result.ok
    assert "unsupported AI hint" in result.ignored_hints[0]
