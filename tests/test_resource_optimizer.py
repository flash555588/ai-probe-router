"""Tests for advisory resource optimization reports."""

import json

from ai_probe_router.solvers.bus_allocator import BusAllocationResult, BusAssignment
from ai_probe_router.solvers.power_domain_solver import (
    PowerAllocationResult,
    PowerDomainStatus,
)
from ai_probe_router.solvers.resource_allocator import ResourceAllocationResult
from ai_probe_router.solvers.resource_allocator_report import (
    write_resource_allocation_report,
)
from ai_probe_router.solvers.resource_optimizer import (
    generate_resource_optimization_report,
)


def test_optimizer_flags_near_limit_power_domain():
    allocation = ResourceAllocationResult(
        power_result=PowerAllocationResult(
            domains=[
                PowerDomainStatus(
                    domain_name="VDD_3V3",
                    voltage=3.3,
                    budget_ma=100.0,
                    requested_ma=90.0,
                    headroom_percent=10.0,
                )
            ],
            near_limit_domains=[
                PowerDomainStatus(
                    domain_name="VDD_3V3",
                    voltage=3.3,
                    budget_ma=100.0,
                    requested_ma=90.0,
                    headroom_percent=10.0,
                )
            ],
        )
    )

    report = generate_resource_optimization_report(allocation)

    assert report.ok
    assert len(report.warnings) == 1
    rec = report.warnings[0]
    assert rec.category == "power"
    assert rec.scope == "VDD_3V3"
    assert not rec.safe_to_apply_automatically


def test_optimizer_recommends_bus_split_when_bus_is_crowded():
    allocation = ResourceAllocationResult(
        bus_result=BusAllocationResult(
            assignments=[
                BusAssignment(
                    bus_type="i2c",
                    bus_id=1,
                    module_name=f"sensor_{index}",
                    instance_id=f"U{index}",
                    address=f"0x5{index}",
                )
                for index in range(5)
            ],
            near_limit=True,
        )
    )

    report = generate_resource_optimization_report(allocation)

    assert len(report.warnings) == 1
    rec = report.warnings[0]
    assert rec.category == "bus"
    assert rec.scope == "I2C-1"
    assert "I2C-2" in rec.recommendation
    assert "sensor_0" in rec.applies_to


def test_resource_report_writer_emits_optimization_report(tmp_path):
    allocation = ResourceAllocationResult(
        bus_result=BusAllocationResult(
            assignments=[
                BusAssignment(
                    bus_type="spi",
                    bus_id=1,
                    module_name=f"flash_{index}",
                    instance_id=f"U{index}",
                )
                for index in range(4)
            ],
            near_limit=True,
        )
    )

    write_resource_allocation_report(allocation, tmp_path)

    payload = json.loads(
        (tmp_path / "resource_optimization_report.json").read_text(encoding="utf-8")
    )
    assert payload["schema_version"] == 1
    assert payload["summary"]["recommendations"] == 1
    assert payload["recommendations"][0]["safe_to_apply_automatically"] is False
