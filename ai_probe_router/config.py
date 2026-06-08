"""Load project YAML configuration into typed models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .models.constraints import Constraints, PlacementRules, RoutingRules
from .models.design_graph import (
    DesignGoals,
    HardwarePlatform,
    ModulePlacementRules,
    RoutingStrategy,
)
from .models.dev_board import DevelopmentBoard
from .models.impedance_control import DiffPairImpedance, ImpedanceControl
from .models.mcu_profile import McuProfile, load_mcu_profile
from .models.module import FunctionalModule, parse_functional_module
from .models.power_domain import PowerDomain
from .models.probe import ProbeConfig, ProbeRequirement, ProbeStyle
from .models.process_control import ProcessControls, ProcessWaiver
from .models.protection import (
    ProtectionComponent,
    ProtectionRules,
    ProtectionType,
    protection_type_from_string,
)
from .models.thermal_analysis import ThermalAnalysis
from .solvers.pin_mapper import load_dev_board


@dataclass
class ResourceAllocatorConfig:
    enable: bool = False
    bus_allocation_strategy: str = "first_fit"
    power_allocation_strategy: str = "max_headroom"
    connector_allocation_strategy: str = "minimize_spread"
    allow_partial_allocation: bool = False

@dataclass
class ModuleFootprintPreviewConfig:
    enable: bool = False
    mode: str = "preview"          # preview | emit_candidate
    write_candidate_pcb: bool = False
    block_on_collision: bool = True
    block_on_missing_footprint: bool = False
    block_on_keepout_violation: bool = True
    candidate_suffix: str = ".module-preview"


@dataclass
class ProjectConfig:
    schema_version: int = 1
    eda_tool: str = "kicad"
    board_file: str = ""
    schematic_file: str = ""
    design_goals: DesignGoals = field(default_factory=DesignGoals)
    hardware_platform: HardwarePlatform = field(default_factory=HardwarePlatform)
    functional_modules: list[FunctionalModule] = field(default_factory=list)
    module_placement: ModulePlacementRules = field(default_factory=ModulePlacementRules)
    routing_strategy: RoutingStrategy = field(default_factory=RoutingStrategy)
    probe: ProbeConfig = field(default_factory=ProbeConfig)
    nets_to_expose: list[ProbeRequirement] = field(default_factory=list)
    constraints: Constraints = field(default_factory=Constraints)
    development_board: DevelopmentBoard | None = None
    protection: ProtectionRules = field(default_factory=ProtectionRules)
    mcu_profile: McuProfile | None = None
    impedance_control: ImpedanceControl = field(default_factory=ImpedanceControl)
    resource_allocator: ResourceAllocatorConfig = field(
        default_factory=ResourceAllocatorConfig
    )
    module_footprint_preview: ModuleFootprintPreviewConfig = field(
        default_factory=ModuleFootprintPreviewConfig
    )
    thermal_analysis: ThermalAnalysis = field(default_factory=ThermalAnalysis)
    process_controls: ProcessControls = field(default_factory=ProcessControls)


def load_config(path: str | Path) -> ProjectConfig:
    text = Path(path).read_text(encoding="utf-8")
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ValueError("Config must be a YAML mapping")
    proj = raw.get("project", {})
    cfg = ProjectConfig(
        schema_version=int(raw.get("schema_version", 1) or 1),
        eda_tool=proj.get("eda_tool", "kicad"),
        board_file=proj.get("board_file", ""),
        schematic_file=proj.get("schematic_file", ""),
    )
    dg = raw.get("design_goals", {})
    cfg.design_goals = DesignGoals(
        optimize_for=[str(v) for v in dg.get("optimize_for", [])],
        max_added_area_mm2=float(dg.get("max_added_area_mm2", 0.0) or 0.0),
        preferred_side=str(dg.get("preferred_side", "")),
        human_review_required_for=[
            str(v) for v in dg.get("human_review_required_for", [])
        ],
    )
    hp = raw.get("hardware_platform", {})
    cfg.hardware_platform = HardwarePlatform(
        target_voltage_domains=[
            PowerDomain(
                name=str(domain.get("name", "")),
                voltage=float(domain.get("voltage", 0.0) or 0.0),
                max_current_ma=float(domain.get("max_current_ma", 0.0) or 0.0),
            )
            for domain in hp.get("target_voltage_domains", [])
            if isinstance(domain, dict)
        ]
    )
    cfg.functional_modules = [
        parse_functional_module(module)
        for module in raw.get("functional_modules", [])
        if isinstance(module, dict)
    ]
    mp = raw.get("module_placement", {})
    cfg.module_placement = ModulePlacementRules(
        group_by_module=mp.get("group_by_module", True),
        keep_power_modules_near_input=mp.get("keep_power_modules_near_input", True),
        keep_analog_modules_away_from_switching_power=mp.get(
            "keep_analog_modules_away_from_switching_power", True,
        ),
        keep_debug_near_board_edge=mp.get("keep_debug_near_board_edge", True),
        max_module_to_probe_distance_mm=float(
            mp.get("max_module_to_probe_distance_mm", 0.0) or 0.0,
        ),
    )
    rs = raw.get("routing_strategy", {})
    cfg.routing_strategy = RoutingStrategy(
        coarse_grid_mm=float(rs.get("coarse_grid_mm", 5.0) or 5.0),
        max_corridor_layers=int(rs.get("max_corridor_layers", 2) or 2),
        congestion_weight=float(rs.get("congestion_weight", 10.0) or 10.0),
        via_weight=float(rs.get("via_weight", 8.0) or 8.0),
        length_weight=float(rs.get("length_weight", 1.0) or 1.0),
        sensitive_net_spacing_mm=float(
            rs.get("sensitive_net_spacing_mm", 5.0) or 5.0,
        ),
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
    nets_to_expose = raw.get("nets_to_expose", [])
    if not nets_to_expose and not cfg.functional_modules:
        raise ValueError(
            "Configuration must specify at least one net in 'nets_to_expose' "
            "or one entry in 'functional_modules'"
        )
    for net_entry in nets_to_expose:
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
        else:
            raise ValueError(
                f"Development board pin database not found: {resolved}"
            )

    prot = raw.get("protection", {})
    if prot:
        enabled = prot.get("enabled", True)
        rules: dict[str, ProtectionComponent] = {}
        for role, spec in prot.items():
            if role == "enabled" or not isinstance(spec, dict):
                continue
            ptype = protection_type_from_string(spec.get("type", "series_resistor"))
            default_prefix = {
                ProtectionType.FERRITE_BEAD: "FB",
                ProtectionType.ESD_ARRAY: "D",
                ProtectionType.TVS_DIODE: "D",
                ProtectionType.LEVEL_SHIFTER: "U",
                ProtectionType.CURRENT_LIMITER: "U",
                ProtectionType.EFUSE: "U",
                ProtectionType.JUMPER: "JP",
            }.get(ptype, "R")
            rules[role] = ProtectionComponent(
                protection_type=ptype,
                value=str(spec.get("value", "33")),
                package=spec.get("package", "0402"),
                ref_prefix=spec.get("ref_prefix", default_prefix),
            )
        cfg.protection = ProtectionRules(rules=rules, enabled=enabled)

    mcu_path = proj.get("mcu_profile", "")
    if mcu_path:
        resolved = Path(path).parent / mcu_path
        if resolved.exists():
            cfg.mcu_profile = load_mcu_profile(resolved)
        else:
            raise ValueError(f"MCU profile not found: {resolved}")

    ic = raw.get("impedance_control", {})
    if ic:
        rules: dict[str, DiffPairImpedance] = {}
        for name, spec in ic.items():
            if isinstance(spec, dict):
                rules[name] = DiffPairImpedance(
                    target_impedance_ohm=float(spec.get("target_impedance_ohm", 90.0) or 90.0),
                    tolerance_percent=float(spec.get("tolerance_percent", 10.0) or 10.0),
                    diff_pair_width_mm=float(spec.get("diff_pair_width_mm", 0.15) or 0.15),
                    diff_pair_gap_mm=float(spec.get("diff_pair_gap_mm", 0.15) or 0.15),
                )
        cfg.impedance_control = ImpedanceControl(rules=rules)

    th = raw.get("thermal_analysis", {})
    if th:
        cfg.thermal_analysis = ThermalAnalysis(
            enabled=bool(th.get("enabled", False)),
            max_junction_temp_c=float(th.get("max_junction_temp_c", 125.0) or 125.0),
            ambient_temp_c=float(th.get("ambient_temp_c", 25.0) or 25.0),
            output_format=str(th.get("output_format", "csv")),
        )

    ra = raw.get("resource_allocator", {})
    if isinstance(ra, dict):
        cfg.resource_allocator = ResourceAllocatorConfig(
            enable=bool(ra.get("enable", False)),
            bus_allocation_strategy=str(ra.get("bus_allocation_strategy", "first_fit")),
            power_allocation_strategy=str(ra.get("power_allocation_strategy", "max_headroom")),
            connector_allocation_strategy=str(
                ra.get("connector_allocation_strategy", "minimize_spread")
            ),
            allow_partial_allocation=bool(ra.get("allow_partial_allocation", False)),
        )

    pc = raw.get("process_controls", {})
    if isinstance(pc, dict):
        waiver_rows = pc.get("waivers", raw.get("waivers", []))
        cfg.process_controls = ProcessControls(
            waivers=[
                _parse_process_waiver(row)
                for row in waiver_rows
                if isinstance(row, dict)
            ],
            strict_signoff=bool(pc.get("strict_signoff", False)),
            require_autorouter_feedback=bool(
                pc.get("require_autorouter_feedback", False),
            ),
            require_manufacturing_exports=bool(
                pc.get("require_manufacturing_exports", False),
            ),
            scalability_module_warning_threshold=int(
                pc.get("scalability_module_warning_threshold", 20) or 20,
            ),
            scalability_net_warning_threshold=int(
                pc.get("scalability_net_warning_threshold", 200) or 200,
            ),
            params={
                k: v for k, v in pc.items()
                if k not in {
                    "waivers",
                    "strict_signoff",
                    "require_autorouter_feedback",
                    "require_manufacturing_exports",
                    "scalability_module_warning_threshold",
                    "scalability_net_warning_threshold",
                }
            },
        )
    elif raw.get("waivers"):
        cfg.process_controls.waivers = [
            _parse_process_waiver(row)
            for row in raw.get("waivers", [])
            if isinstance(row, dict)
        ]

    mfp = raw.get("module_footprint_preview", {})
    if isinstance(mfp, dict):
        cfg.module_footprint_preview = ModuleFootprintPreviewConfig(
            enable=bool(mfp.get("enable", False)),
            mode=str(mfp.get("mode", "preview")),
            write_candidate_pcb=bool(mfp.get("write_candidate_pcb", False)),
            block_on_collision=bool(mfp.get("block_on_collision", True)),
            block_on_missing_footprint=bool(
                mfp.get("block_on_missing_footprint", False)
            ),
            block_on_keepout_violation=bool(
                mfp.get("block_on_keepout_violation", True)
            ),
            candidate_suffix=str(mfp.get("candidate_suffix", ".module-preview")),
        )
    return cfg


def _parse_process_waiver(raw: dict) -> ProcessWaiver:
    return ProcessWaiver(
        waiver_id=str(raw.get("id", raw.get("waiver_id", ""))),
        source=str(raw.get("source", "")),
        issue_id=str(raw.get("issue_id", "")),
        reason=str(raw.get("reason", "")),
        owner=str(raw.get("owner", raw.get("approved_by", ""))),
        expires_on=str(raw.get("expires_on", raw.get("expires", ""))),
    )
