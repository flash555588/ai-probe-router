"""Load project YAML configuration into typed models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .models.constraints import Constraints, PlacementRules, RoutingRules
from .models.dev_board import DevelopmentBoard
from .models.probe import ProbeConfig, ProbeRequirement, ProbeStyle
from .models.protection import (
    ProtectionComponent,
    ProtectionRules,
    ProtectionType,
)
from .solvers.pin_mapper import load_dev_board


@dataclass
class ProjectConfig:
    eda_tool: str = "kicad"
    board_file: str = ""
    schematic_file: str = ""
    probe: ProbeConfig = field(default_factory=ProbeConfig)
    nets_to_expose: list[ProbeRequirement] = field(default_factory=list)
    constraints: Constraints = field(default_factory=Constraints)
    development_board: DevelopmentBoard | None = None
    dev_board_pin_db: str = ""
    protection: ProtectionRules = field(default_factory=ProtectionRules.with_defaults)


def load_config(path: str | Path) -> ProjectConfig:
    text = Path(path).read_text(encoding="utf-8")
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ValueError("Config must be a YAML mapping")
    proj = raw.get("project", {})
    cfg = ProjectConfig(
        eda_tool=proj.get("eda_tool", "kicad"),
        board_file=proj.get("board_file", ""),
        schematic_file=proj.get("schematic_file", ""),
    )
    pi = raw.get("probe_interface", {})
    style_map = {"test_pad": ProbeStyle.TEST_PAD, "pogo_pad_array": ProbeStyle.POGO_PAD,
                 "connector": ProbeStyle.CONNECTOR}
    cfg.probe = ProbeConfig(
        style=style_map.get(pi.get("type", "test_pad"), ProbeStyle.TEST_PAD),
        side=pi.get("side", "top"),
        pad_diameter_mm=pi.get("pad_diameter_mm", 1.5),
        min_spacing_mm=pi.get("min_probe_spacing_mm", 2.54),
        preferred_grid_mm=pi.get("preferred_grid_mm", 2.54),
        require_silkscreen_labels=pi.get("require_silkscreen_labels", True),
        require_fiducials=pi.get("require_fiducials", False),
        require_tooling_holes=pi.get("require_tooling_holes", False),
    )
    for net_entry in raw.get("nets_to_expose", []):
        cfg.nets_to_expose.append(ProbeRequirement(
            net_name=net_entry.get("net", ""),
            role=net_entry.get("role", "digital"),
            required=net_entry.get("required", True),
            preferred_devboard_pins=net_entry.get("preferred_devboard_pins", []),
            duplicate_probe_count=net_entry.get("duplicate_probe_count", 1),
            current_ma=net_entry.get("current_ma", 0),
            pair_net_name=net_entry.get("pair_with", ""),
        ))
    rr = raw.get("routing_rules", {})
    cfg.constraints.routing = RoutingRules(
        default_trace_width_mm=rr.get("default_trace_width_mm", 0.15),
        power_trace_width_mm=rr.get("power_trace_width_mm", 0.5),
        min_clearance_mm=rr.get("min_clearance_mm", 0.15),
        max_vias_per_signal=rr.get("max_vias_per_signal", 2),
        avoid_under_components=rr.get("avoid_under_components", True),
    )
    pr = raw.get("placement_rules", {})
    cfg.constraints.placement = PlacementRules(
        keep_probe_pads_on_grid=pr.get("keep_probe_pads_on_grid", True),
        avoid_tall_components=pr.get("avoid_tall_components", True),
        min_distance_from_board_edge_mm=pr.get("min_distance_from_board_edge_mm", 2.0),
        group_by_function=pr.get("group_by_function", True),
    )
    db = raw.get("development_board", {})
    db_path = db.get("pin_database", "")
    if db_path:
        cfg.dev_board_pin_db = db_path
        resolved = Path(path).parent / db_path
        if resolved.exists():
            cfg.development_board = load_dev_board(resolved)

    prot = raw.get("protection", {})
    if prot:
        enabled = prot.get("enabled", True)
        rules: dict[str, ProtectionComponent] = {}
        type_map = {
            "series_resistor": ProtectionType.SERIES_RESISTOR,
            "ferrite_bead": ProtectionType.FERRITE_BEAD,
        }
        for role, spec in prot.items():
            if role == "enabled" or not isinstance(spec, dict):
                continue
            ptype = type_map.get(spec.get("type", "series_resistor"),
                                ProtectionType.SERIES_RESISTOR)
            is_resistor = ptype == ProtectionType.SERIES_RESISTOR
            default_prefix = "R" if is_resistor else "FB"
            rules[role] = ProtectionComponent(
                protection_type=ptype,
                value=str(spec.get("value", "33")),
                package=spec.get("package", "0402"),
                ref_prefix=spec.get("ref_prefix", default_prefix),
            )
        cfg.protection = ProtectionRules(rules=rules, enabled=enabled)

    return cfg
