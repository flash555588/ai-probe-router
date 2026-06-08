"""Bus allocator for I2C/SPI/UART shared-bus assignment."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models.module import SelectedModule


@dataclass(frozen=True)
class BusConflict:
    bus_type: str
    address: str
    modules: list[str]


@dataclass
class BusAssignment:
    bus_type: str
    bus_id: int
    module_name: str
    instance_id: str
    address: str = ""


@dataclass
class BusAllocationResult:
    assignments: list[BusAssignment] = field(default_factory=list)
    conflicts: list[BusConflict] = field(default_factory=list)
    near_limit: bool = False


_BUS_TYPES = {"i2c", "spi", "uart"}


def allocate_buses(
    modules: list[SelectedModule],
    strategy: str = "first_fit",
) -> BusAllocationResult:
    """Assign modules to shared buses, checking for address conflicts.

    * strategy='first_fit' — pack onto the first bus with room.
    * strategy='best_fit'  — pack onto the bus with the most room.
    """
    result = BusAllocationResult()
    bus_counters: dict[str, int] = {}
    bus_occupancy: dict[tuple[str, int], list[tuple[str, str]]] = {}
    address_map: dict[tuple[str, int, str], list[str]] = {}

    for sel in modules:
        mod = sel.module
        impl = sel.implementation
        instance_id = getattr(sel, "instance_id", mod.name)
        required_buses = _required_buses_for_module(mod, impl)
        for bus_type in required_buses:
            if bus_type not in _BUS_TYPES:
                continue
            assigned = False
            candidate_buses = sorted(
                [b for b in bus_occupancy if b[0] == bus_type],
                key=lambda b: len(bus_occupancy[b]),
            )
            if strategy == "best_fit" and candidate_buses:
                candidate_buses = sorted(
                    candidate_buses,
                    key=lambda b: len(bus_occupancy[b]),
                    reverse=True,
                )
            for bus_key in candidate_buses:
                addr = _i2c_address_for(sel) if bus_type == "i2c" else ""
                if addr and bus_type == "i2c":
                    existing = address_map.get((bus_type, bus_key[1], addr), [])
                    if existing:
                        continue  # conflict on this bus
                bus_occupancy[bus_key].append((mod.name, instance_id))
                if addr:
                    address_map.setdefault((bus_type, bus_key[1], addr), []).append(
                        f"{instance_id}:{mod.name}"
                    )
                result.assignments.append(
                    BusAssignment(
                        bus_type=bus_type,
                        bus_id=bus_key[1],
                        module_name=mod.name,
                        instance_id=instance_id,
                        address=addr,
                    )
                )
                assigned = True
                break
            if not assigned:
                bus_id = bus_counters.get(bus_type, 0) + 1
                bus_counters[bus_type] = bus_id
                bus_key = (bus_type, bus_id)
                bus_occupancy[bus_key] = [(mod.name, instance_id)]
                addr = _i2c_address_for(sel) if bus_type == "i2c" else ""
                if addr:
                    address_map.setdefault((bus_type, bus_id, addr), []).append(
                        f"{instance_id}:{mod.name}"
                    )
                result.assignments.append(
                    BusAssignment(
                        bus_type=bus_type,
                        bus_id=bus_id,
                        module_name=mod.name,
                        instance_id=instance_id,
                        address=addr,
                    )
                )

    # Detect unresolved address conflicts
    for (bus_type, bus_id, addr), mods in address_map.items():
        if len(mods) > 1:
            result.conflicts.append(
                BusConflict(
                    bus_type=bus_type,
                    address=addr,
                    modules=mods,
                )
            )

    # Near-limit: any bus with >3 modules or any I2C bus with >5 addresses
    for bus_key, occupants in bus_occupancy.items():
        bus_type = bus_key[0]
        limit = 5 if bus_type == "i2c" else 4
        if len(occupants) >= limit:
            result.near_limit = True
            break

    return result


def _required_buses_for_module(mod, impl) -> list[str]:
    """Infer bus types from module interfaces."""
    buses: set[str] = set()
    if impl and impl.interfaces:
        for iface in impl.interfaces:
            iface_lower = str(iface).lower()
            if "i2c" in iface_lower:
                buses.add("i2c")
            elif "spi" in iface_lower:
                buses.add("spi")
            elif "uart" in iface_lower:
                buses.add("uart")
    # Fallback: inspect module provides
    for p in (getattr(mod, "provides", []) or []):
        p_lower = str(p).lower()
        if "i2c" in p_lower:
            buses.add("i2c")
        elif "spi" in p_lower:
            buses.add("spi")
        elif "uart" in p_lower:
            buses.add("uart")
    return sorted(buses)


def _i2c_address_for(sel: SelectedModule) -> str:
    """Extract I2C address from module constraints or params."""
    addr = sel.module.params.get("i2c_address", "")
    if addr:
        return str(addr)
    # Try implementation constraints
    impl = sel.implementation
    if impl and impl.constraints:
        addr = impl.constraints.get("i2c_address", "")
        if addr:
            return str(addr)
    return ""
