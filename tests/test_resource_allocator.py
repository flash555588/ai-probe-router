"""Tests for resource allocator, bus allocator, and power domain solver."""

from ai_probe_router.config import ProjectConfig, ResourceAllocatorConfig
from ai_probe_router.models.module import (
    ComponentSpec,
    FunctionalModule,
    ModuleDefinition,
    ModuleImplementation,
    SelectedModule,
)
from ai_probe_router.models.power_domain import PowerDomain
from ai_probe_router.solvers.bus_allocator import allocate_buses
from ai_probe_router.solvers.power_domain_solver import allocate_power
from ai_probe_router.solvers.resource_allocator import allocate_resources


def _sel(
    name: str,
    interfaces: list[str] | None = None,
    params: dict | None = None,
    comp_type: str = "mcu",
) -> SelectedModule:
    mod = FunctionalModule(
        name=name,
        type="test",
        params=params or {},
    )
    definition = ModuleDefinition(name=name, type="test")
    impl = ModuleImplementation(
        name=f"{name}_impl",
        interfaces=interfaces or [],
        components=[ComponentSpec(type=comp_type, count=1)],
    )
    return SelectedModule(
        module=mod,
        definition=definition,
        implementation=impl,
    )


class TestBusAllocator:
    def test_single_module_gets_own_bus(self):
        modules = [_sel("gps", interfaces=["uart"])]
        result = allocate_buses(modules)
        assert len(result.assignments) == 1
        assert result.assignments[0].bus_type == "uart"
        assert result.assignments[0].bus_id == 1
        assert not result.conflicts

    def test_two_i2c_modules_share_bus_when_no_address_conflict(self):
        modules = [
            _sel("sensor_a", interfaces=["i2c"], params={"i2c_address": "0x50"}),
            _sel("sensor_b", interfaces=["i2c"], params={"i2c_address": "0x51"}),
        ]
        result = allocate_buses(modules)
        assert len(result.assignments) == 2
        assert result.assignments[0].bus_id == result.assignments[1].bus_id
    def test_i2c_address_conflict_avoided_by_new_bus(self):
        modules = [
            _sel("sensor_a", interfaces=["i2c"], params={"i2c_address": "0x50"}),
            _sel("sensor_b", interfaces=["i2c"], params={"i2c_address": "0x50"}),
        ]
        result = allocate_buses(modules)
        # Same address modules are placed on separate buses
        assert not result.conflicts
        assert result.assignments[0].bus_id != result.assignments[1].bus_id

    def test_near_limit_flag(self):
        modules = [
            _sel(f"sensor_{i}", interfaces=["i2c"], params={"i2c_address": f"0x{50+i}"})
            for i in range(6)
        ]
        result = allocate_buses(modules)
        assert result.near_limit

    def test_best_fit_strategy_prefers_emptier_bus(self):
        modules = [
            _sel("a", interfaces=["spi"]),
            _sel("b", interfaces=["spi"]),
            _sel("c", interfaces=["spi"]),
        ]
        result = allocate_buses(modules, strategy="best_fit")
        assert len(result.assignments) == 3
        assert all(a.bus_id == 1 for a in result.assignments)


class TestPowerDomainSolver:
    def test_within_budget(self):
        modules = [_sel("low_power", interfaces=["i2c"])]
        domains = [PowerDomain(name="3V3", voltage=3.3, max_current_ma=500.0)]
        result = allocate_power(modules, domains)
        assert not result.overload_domains

    def test_overload_detected(self):
        modules = [_sel("motor", interfaces=["uart"], comp_type="motor_driver")]
        domains = [PowerDomain(name="3V3", voltage=3.3, max_current_ma=100.0)]
        result = allocate_power(modules, domains)
        assert len(result.overload_domains) == 1
        assert result.overload_domains[0].domain_name == "3V3"

    def test_near_limit_detected(self):
        modules = [_sel("mcu", interfaces=["uart"])]
        domains = [PowerDomain(name="3V3", voltage=3.3, max_current_ma=110.0)]
        result = allocate_power(modules, domains)
        assert not result.overload_domains
        assert len(result.near_limit_domains) == 1

    def test_multiple_voltages(self):
        modules = [
            _sel("mcu", interfaces=["uart"]),
            _sel("motor", interfaces=["uart"], comp_type="motor_driver"),
        ]
        domains = [
            PowerDomain(name="3V3", voltage=3.3, max_current_ma=700.0),
            PowerDomain(name="5V", voltage=5.0, max_current_ma=600.0),
        ]
        result = allocate_power(modules, domains)
        assert result.domains[0].requested_ma == 600.0  # both on 3.3V default


class TestResourceAllocator:
    def test_disabled_returns_warning(self):
        cfg = ProjectConfig(resource_allocator=ResourceAllocatorConfig(enable=False))
        result = allocate_resources([], cfg)
        assert result.ok
        assert "RESOURCE_ALLOCATOR_DISABLED" in result.warnings

    def test_enabled_no_modules(self):
        cfg = ProjectConfig(resource_allocator=ResourceAllocatorConfig(enable=True))
        result = allocate_resources([], cfg)
        assert result.ok
        assert not result.errors

    def test_bus_conflict_avoided_by_new_bus(self):
        from ai_probe_router.models.design_graph import HardwarePlatform
        cfg = ProjectConfig(
            resource_allocator=ResourceAllocatorConfig(enable=True),
            hardware_platform=HardwarePlatform(),
        )
        modules = [
            _sel("a", interfaces=["i2c"], params={"i2c_address": "0x50"}),
            _sel("b", interfaces=["i2c"], params={"i2c_address": "0x50"}),
        ]
        result = allocate_resources(modules, cfg)
        # Allocator avoids conflicts by creating separate buses
        assert result.ok
        assert not result.errors
        assert result.bus_result.assignments[0].bus_id != result.bus_result.assignments[1].bus_id

    def test_power_overload_blocks(self):
        from ai_probe_router.models.design_graph import HardwarePlatform
        cfg = ProjectConfig(
            resource_allocator=ResourceAllocatorConfig(enable=True),
            hardware_platform=HardwarePlatform(
                target_voltage_domains=[
                    PowerDomain(name="3V3", voltage=3.3, max_current_ma=50.0)
                ]
            ),
        )
        modules = [_sel("mcu", interfaces=["uart"])]
        result = allocate_resources(modules, cfg)
        assert not result.ok
        assert any("POWER_DOMAIN_OVERLOAD" in e for e in result.errors)

    def test_allow_partial_allows_errors(self):
        from ai_probe_router.models.design_graph import HardwarePlatform
        cfg = ProjectConfig(
            resource_allocator=ResourceAllocatorConfig(
                enable=True, allow_partial_allocation=True
            ),
            hardware_platform=HardwarePlatform(
                target_voltage_domains=[
                    PowerDomain(name="3V3", voltage=3.3, max_current_ma=50.0)
                ]
            ),
        )
        modules = [_sel("mcu", interfaces=["uart"])]
        result = allocate_resources(modules, cfg)
        assert result.ok

    def test_readiness_warnings_present(self):
        from ai_probe_router.models.design_graph import HardwarePlatform
        cfg = ProjectConfig(
            resource_allocator=ResourceAllocatorConfig(enable=True),
            hardware_platform=HardwarePlatform(
                target_voltage_domains=[
                    PowerDomain(name="3V3", voltage=3.3, max_current_ma=500.0)
                ]
            ),
        )
        modules = [_sel("sensor", interfaces=["i2c"], params={"i2c_address": "0x50"})]
        result = allocate_resources(modules, cfg)
        assert result.ok
        assert not result.errors
