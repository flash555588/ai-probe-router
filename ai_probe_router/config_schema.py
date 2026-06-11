"""Validate YAML configuration shape before mapping it to domain models."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class ConfigValidationError(ValueError):
    """Raised when configuration YAML does not match the supported contract."""


_SUPPORTED_SCHEMA_VERSIONS = {1, 2}
_TOP_LEVEL_SECTION_TYPES: dict[str, type | tuple[type, ...]] = {
    "project": dict,
    "design_goals": dict,
    "hardware_platform": dict,
    "crystal": dict,
    "functional_modules": list,
    "module_placement": dict,
    "routing_strategy": dict,
    "probe_interface": dict,
    "nets_to_expose": list,
    "routing_rules": dict,
    "placement_rules": dict,
    "fabrication": dict,
    "development_board": dict,
    "protection": dict,
    "impedance_control": dict,
    "thermal_analysis": dict,
    "resource_allocator": dict,
    "process_controls": dict,
    "waivers": list,
    "module_footprint_preview": dict,
    "plugin_shell": dict,
    "dry_run": bool,
}
_TOP_LEVEL_KEYS = set(_TOP_LEVEL_SECTION_TYPES) | {"schema_version"}
_TEXT_TYPES = (str, int, float)
_PROJECT_KEYS = {
    "board_file",
    "description",
    "eda_tool",
    "mcu_profile",
    "name",
    "output_dir",
    "schematic_file",
}
_DESIGN_GOAL_KEYS = {
    "constraints",
    "human_review_required_for",
    "max_added_area_mm2",
    "optimize_for",
    "preferred_side",
}
_DESIGN_GOAL_CONSTRAINT_KEYS = {
    "max_board_area_mm2",
    "max_layer_count",
    "min_trace_width_mm",
    "preferred_via_size_mm",
}
_HARDWARE_PLATFORM_KEYS = {"mcu_profile", "target_voltage_domains"}
_POWER_DOMAIN_KEYS = {"max_current_ma", "name", "voltage"}
_FUNCTIONAL_MODULE_KEYS = {
    "ai_hints",
    "allowed_implementations",
    "allowed_interfaces",
    "budget_area_mm2",
    "channels",
    "constraints",
    "depends_on",
    "name",
    "params",
    "preferred_region",
    "priority",
    "rails",
    "require_esd",
    "require_input_protection",
    "require_level_shift",
    "require_mux",
    "required",
    "resolution_bits_min",
    "target_nets",
    "telemetry_bus",
    "type",
    "version",
    "voltage_domains",
}
_AI_HINT_KEYS = {
    "params",
    "target",
    "type",
    "value",
}
_MODULE_PLACEMENT_KEYS = {
    "group_by_module",
    "keep_analog_modules_away_from_switching_power",
    "keep_debug_near_board_edge",
    "keep_power_modules_near_input",
    "max_module_to_probe_distance_mm",
}
_ROUTING_STRATEGY_KEYS = {
    "coarse_grid_mm",
    "congestion_weight",
    "length_weight",
    "max_corridor_layers",
    "sensitive_net_spacing_mm",
    "via_weight",
}
_PROBE_INTERFACE_KEYS = {
    "min_probe_spacing_mm",
    "pad_diameter_mm",
    "preferred_grid_mm",
    "require_fiducials",
    "require_silkscreen_labels",
    "require_tooling_holes",
    "side",
    "type",
}
_NET_KEYS = {
    "current_ma",
    "duplicate_probe_count",
    "net",
    "pair_with",
    "preferred_devboard_pins",
    "required",
    "role",
}
_ROUTING_RULE_KEYS = {
    "analog_trace_width_mm",
    "avoid_under_components",
    "backend",
    "default_trace_width_mm",
    "diff_pair_routing",
    "max_vias_per_signal",
    "min_clearance_mm",
    "power_trace_width_mm",
}
_DIFF_PAIR_ROUTING_KEYS = {
    "gap_mm",
    "impedance_ohm",
    "max_skew_ps",
    "min_gap_mm",
    "trace_width_mm",
}
_FABRICATION_KEYS = {
    "min_clearance_mm",
    "min_drill_mm",
    "min_trace_width_mm",
    "preferred_via_drill_mm",
    "soldermask_expansion_mm",
}
_PLACEMENT_RULE_KEYS = {
    "avoid_tall_components",
    "digital_analog_separation",
    "group_by_function",
    "keep_probe_pads_on_grid",
    "min_distance_from_board_edge_mm",
}
_DIGITAL_ANALOG_SEPARATION_KEYS = {
    "analog_region",
    "digital_region",
    "enabled",
    "ground_stitch_via_spacing_mm",
    "isolation_gap_mm",
    "split_direction",
}
_DEVELOPMENT_BOARD_KEYS = {"pin_database"}
_PROTECTION_SPEC_KEYS = {
    "notes",
    "package",
    "part",
    "ptc_fuse",
    "ref_prefix",
    "schottky",
    "stages",
    "tvs",
    "type",
    "value",
}
_IMPEDANCE_RULE_KEYS = {
    "diff_pair_gap_mm",
    "diff_pair_width_mm",
    "target_impedance_ohm",
    "tolerance_percent",
}
_THERMAL_ANALYSIS_KEYS = {
    "ambient_temp_c",
    "enabled",
    "max_junction_temp_c",
    "output_format",
}
_RESOURCE_ALLOCATOR_KEYS = {
    "allow_partial_allocation",
    "bus_allocation_strategy",
    "connector_allocation_strategy",
    "enable",
    "near_limit_threshold",
    "overload_block",
    "power_allocation_strategy",
}
_PROCESS_CONTROL_KEYS = {
    "params",
    "require_autorouter_feedback",
    "require_manufacturing_exports",
    "scalability_module_warning_threshold",
    "scalability_net_warning_threshold",
    "strict_signoff",
    "waivers",
}
_PROCESS_WAIVER_KEYS = {
    "approved_by",
    "expires",
    "expires_on",
    "id",
    "issue_id",
    "owner",
    "reason",
    "source",
    "waiver_id",
}
_MODULE_FOOTPRINT_PREVIEW_KEYS = {
    "block_on_collision",
    "block_on_keepout_violation",
    "block_on_missing_footprint",
    "candidate_suffix",
    "enable",
    "enabled",
    "mode",
    "write_candidate_pcb",
}
_PLUGIN_SHELL_KEYS = {
    "enable_3d",
    "fallback_to_2d_board",
    "step_file",
}
_CRYSTAL_KEYS = {
    "frequency_mhz",
    "notes",
    "package",
    "tolerance_ppm",
    "type",
}


def validate_config(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ConfigValidationError("Config must be a YAML mapping")

    _reject_unknown_keys(raw, _TOP_LEVEL_KEYS, "config")
    for key, expected_type in _TOP_LEVEL_SECTION_TYPES.items():
        if key in raw and not isinstance(raw[key], expected_type):
            raise ConfigValidationError(f"{key} must be {_type_name(expected_type)}")

    schema_version = _coerce_int(raw.get("schema_version", 1), "schema_version")
    if schema_version not in _SUPPORTED_SCHEMA_VERSIONS:
        supported = ", ".join(str(version) for version in sorted(_SUPPORTED_SCHEMA_VERSIONS))
        raise ConfigValidationError(
            f"Unsupported schema_version {schema_version}; supported versions: {supported}"
        )

    _validate_project(raw.get("project", {}))
    _validate_design_goals(raw.get("design_goals", {}))
    _validate_hardware_platform(raw.get("hardware_platform", {}))
    _validate_functional_modules(raw.get("functional_modules", []))
    _validate_module_placement(raw.get("module_placement", {}))
    _validate_routing_strategy(raw.get("routing_strategy", {}))
    _validate_probe_interface(raw.get("probe_interface", {}))
    _validate_nets_to_expose(raw.get("nets_to_expose", []))
    _validate_routing_rules(raw.get("routing_rules", {}))
    _validate_placement_rules(raw.get("placement_rules", {}))
    _validate_development_board(raw.get("development_board", {}))
    _validate_fabrication(raw.get("fabrication", {}))
    _validate_crystal(raw.get("crystal", {}))
    _validate_protection(raw.get("protection", {}))
    _validate_impedance_control(raw.get("impedance_control", {}))
    _validate_thermal_analysis(raw.get("thermal_analysis", {}))
    _validate_resource_allocator(raw.get("resource_allocator", {}))
    _validate_process_controls(raw.get("process_controls", {}), raw.get("waivers", []))
    _validate_module_footprint_preview(raw.get("module_footprint_preview", {}))
    _validate_plugin_shell(raw.get("plugin_shell", {}))
    return raw


def _validate_project(raw: Mapping[str, Any]) -> None:
    _reject_unknown_keys(raw, _PROJECT_KEYS, "project")
    _optional_text(raw, "eda_tool", "project.eda_tool")
    if raw.get("eda_tool", "kicad") != "kicad":
        raise ConfigValidationError("project.eda_tool must be 'kicad'")
    _optional_text(raw, "name", "project.name")
    _optional_text(raw, "board_file", "project.board_file")
    _optional_text(raw, "schematic_file", "project.schematic_file")
    _optional_text(raw, "mcu_profile", "project.mcu_profile")
    _optional_text(raw, "output_dir", "project.output_dir")
    _optional_text(raw, "description", "project.description")


def _validate_design_goals(raw: Mapping[str, Any]) -> None:
    _reject_unknown_keys(raw, _DESIGN_GOAL_KEYS, "design_goals")
    _optional_text_list(raw, "optimize_for", "design_goals.optimize_for")
    _optional_number(raw, "max_added_area_mm2", "design_goals.max_added_area_mm2", minimum=0)
    _optional_text(raw, "preferred_side", "design_goals.preferred_side")
    _optional_text_list(
        raw,
        "human_review_required_for",
        "design_goals.human_review_required_for",
    )
    if "constraints" in raw:
        constraints = _require_mapping(raw["constraints"], "design_goals.constraints")
        _reject_unknown_keys(
            constraints,
            _DESIGN_GOAL_CONSTRAINT_KEYS,
            "design_goals.constraints",
        )
        _optional_number(
            constraints,
            "max_board_area_mm2",
            "design_goals.constraints.max_board_area_mm2",
            minimum=0,
        )
        _optional_int(
            constraints,
            "max_layer_count",
            "design_goals.constraints.max_layer_count",
            minimum=1,
        )
        _optional_number(
            constraints,
            "min_trace_width_mm",
            "design_goals.constraints.min_trace_width_mm",
            minimum=0,
        )
        _optional_number(
            constraints,
            "preferred_via_size_mm",
            "design_goals.constraints.preferred_via_size_mm",
            minimum=0,
        )


def _validate_hardware_platform(raw: Mapping[str, Any]) -> None:
    _reject_unknown_keys(raw, _HARDWARE_PLATFORM_KEYS, "hardware_platform")
    _optional_text(raw, "mcu_profile", "hardware_platform.mcu_profile")
    if "target_voltage_domains" not in raw:
        return
    domains = _require_list(
        raw["target_voltage_domains"],
        "hardware_platform.target_voltage_domains",
    )
    for index, domain in enumerate(domains):
        path = f"hardware_platform.target_voltage_domains[{index}]"
        domain = _require_mapping(domain, path)
        _reject_unknown_keys(domain, _POWER_DOMAIN_KEYS, path)
        _optional_text(domain, "name", f"{path}.name")
        _optional_number(domain, "voltage", f"{path}.voltage", minimum=0)
        _optional_number(domain, "max_current_ma", f"{path}.max_current_ma", minimum=0)


def _validate_functional_modules(rows: list[Any]) -> None:
    for index, row in enumerate(rows):
        path = f"functional_modules[{index}]"
        row = _require_mapping(row, path)
        _reject_unknown_keys(row, _FUNCTIONAL_MODULE_KEYS, path)
        _require_non_empty_text(row.get("name"), f"{path}.name")
        _require_non_empty_text(row.get("type"), f"{path}.type")
        _optional_bool(row, "required", f"{path}.required")
        _optional_int(row, "priority", f"{path}.priority")
        _optional_text_list(row, "target_nets", f"{path}.target_nets")
        _optional_text_list(row, "depends_on", f"{path}.depends_on")
        _optional_int(row, "channels", f"{path}.channels", minimum=0)
        _optional_text_list(row, "voltage_domains", f"{path}.voltage_domains")
        _optional_text_list(row, "allowed_implementations", f"{path}.allowed_implementations")
        _optional_text_list(row, "allowed_interfaces", f"{path}.allowed_interfaces")
        _optional_text_list(row, "rails", f"{path}.rails")
        _optional_text(row, "telemetry_bus", f"{path}.telemetry_bus")
        _optional_int(row, "resolution_bits_min", f"{path}.resolution_bits_min", minimum=0)
        _optional_number(row, "budget_area_mm2", f"{path}.budget_area_mm2", minimum=0)
        _optional_text(row, "preferred_region", f"{path}.preferred_region")
        _optional_text(row, "version", f"{path}.version")
        _optional_bool(row, "require_level_shift", f"{path}.require_level_shift")
        _optional_bool(row, "require_esd", f"{path}.require_esd")
        _optional_bool(row, "require_input_protection", f"{path}.require_input_protection")
        _optional_bool(row, "require_mux", f"{path}.require_mux")
        if "ai_hints" in row:
            _validate_ai_hints(row["ai_hints"], f"{path}.ai_hints")
        if "params" in row:
            _require_mapping(row["params"], f"{path}.params")
        if "constraints" in row:
            _require_mapping(row["constraints"], f"{path}.constraints")


def _validate_ai_hints(raw: Any, path: str) -> None:
    hints = _require_list(raw, path)
    for index, hint in enumerate(hints):
        hint_path = f"{path}[{index}]"
        if isinstance(hint, str):
            continue
        hint = _require_mapping(hint, hint_path)
        _reject_unknown_keys(hint, _AI_HINT_KEYS, hint_path)
        _optional_text(hint, "type", f"{hint_path}.type")
        _optional_text(hint, "target", f"{hint_path}.target")
        _optional_text(hint, "value", f"{hint_path}.value")
        if "params" in hint:
            _require_mapping(hint["params"], f"{hint_path}.params")


def _validate_module_placement(raw: Mapping[str, Any]) -> None:
    _reject_unknown_keys(raw, _MODULE_PLACEMENT_KEYS, "module_placement")
    _optional_bool(raw, "group_by_module", "module_placement.group_by_module")
    _optional_bool(
        raw,
        "keep_power_modules_near_input",
        "module_placement.keep_power_modules_near_input",
    )
    _optional_bool(
        raw,
        "keep_analog_modules_away_from_switching_power",
        "module_placement.keep_analog_modules_away_from_switching_power",
    )
    _optional_bool(raw, "keep_debug_near_board_edge", "module_placement.keep_debug_near_board_edge")
    _optional_number(
        raw,
        "max_module_to_probe_distance_mm",
        "module_placement.max_module_to_probe_distance_mm",
        minimum=0,
    )


def _validate_routing_strategy(raw: Mapping[str, Any]) -> None:
    _reject_unknown_keys(raw, _ROUTING_STRATEGY_KEYS, "routing_strategy")
    _optional_number(raw, "coarse_grid_mm", "routing_strategy.coarse_grid_mm", minimum=0)
    _optional_int(raw, "max_corridor_layers", "routing_strategy.max_corridor_layers", minimum=1)
    _optional_number(raw, "congestion_weight", "routing_strategy.congestion_weight", minimum=0)
    _optional_number(raw, "via_weight", "routing_strategy.via_weight", minimum=0)
    _optional_number(raw, "length_weight", "routing_strategy.length_weight", minimum=0)
    _optional_number(
        raw,
        "sensitive_net_spacing_mm",
        "routing_strategy.sensitive_net_spacing_mm",
        minimum=0,
    )


def _validate_probe_interface(raw: Mapping[str, Any]) -> None:
    _reject_unknown_keys(raw, _PROBE_INTERFACE_KEYS, "probe_interface")
    if "type" in raw:
        _optional_text(raw, "type", "probe_interface.type")
        if raw["type"] not in {"test_pad", "pogo_pad_array", "connector"}:
            raise ConfigValidationError(
                "probe_interface.type must be one of: connector, pogo_pad_array, test_pad"
            )
    if "side" in raw:
        _optional_text(raw, "side", "probe_interface.side")
        if raw["side"] not in {"top", "bottom"}:
            raise ConfigValidationError("probe_interface.side must be 'top' or 'bottom'")
    _optional_number(raw, "pad_diameter_mm", "probe_interface.pad_diameter_mm", minimum=0)
    _optional_number(raw, "min_probe_spacing_mm", "probe_interface.min_probe_spacing_mm", minimum=0)
    _optional_number(raw, "preferred_grid_mm", "probe_interface.preferred_grid_mm", minimum=0)
    _optional_bool(
        raw,
        "require_silkscreen_labels",
        "probe_interface.require_silkscreen_labels",
    )
    _optional_bool(raw, "require_fiducials", "probe_interface.require_fiducials")
    _optional_bool(raw, "require_tooling_holes", "probe_interface.require_tooling_holes")


def _validate_nets_to_expose(rows: list[Any]) -> None:
    for index, row in enumerate(rows):
        path = f"nets_to_expose[{index}]"
        row = _require_mapping(row, path)
        _reject_unknown_keys(row, _NET_KEYS, path)
        _require_non_empty_text(row.get("net"), f"{path}.net")
        _optional_text(row, "role", f"{path}.role")
        _optional_bool(row, "required", f"{path}.required")
        _optional_text_list(row, "preferred_devboard_pins", f"{path}.preferred_devboard_pins")
        _optional_int(row, "duplicate_probe_count", f"{path}.duplicate_probe_count", minimum=1)
        _optional_number(row, "current_ma", f"{path}.current_ma", minimum=0)
        _optional_text(row, "pair_with", f"{path}.pair_with")


def _validate_routing_rules(raw: Mapping[str, Any]) -> None:
    _reject_unknown_keys(raw, _ROUTING_RULE_KEYS, "routing_rules")
    _optional_number(
        raw,
        "default_trace_width_mm",
        "routing_rules.default_trace_width_mm",
        minimum=0,
    )
    _optional_number(raw, "power_trace_width_mm", "routing_rules.power_trace_width_mm", minimum=0)
    _optional_number(raw, "min_clearance_mm", "routing_rules.min_clearance_mm", minimum=0)
    _optional_int(raw, "max_vias_per_signal", "routing_rules.max_vias_per_signal", minimum=0)
    _optional_bool(raw, "avoid_under_components", "routing_rules.avoid_under_components")
    backend = raw.get("backend")
    if backend is not None and backend not in {"freerouting", "grid", "auto"}:
        raise ConfigValidationError(
            f"routing_rules.backend must be one of 'freerouting', 'grid', 'auto'; got '{backend}'"
        )
    _optional_number(
        raw,
        "analog_trace_width_mm",
        "routing_rules.analog_trace_width_mm",
        minimum=0,
    )
    if "diff_pair_routing" in raw:
        rules = _require_mapping(raw["diff_pair_routing"], "routing_rules.diff_pair_routing")
        for name, spec in rules.items():
            spec_path = f"routing_rules.diff_pair_routing.{name}"
            spec = _require_mapping(spec, spec_path)
            _reject_unknown_keys(spec, _DIFF_PAIR_ROUTING_KEYS, spec_path)
            _optional_number(spec, "trace_width_mm", f"{spec_path}.trace_width_mm", minimum=0)
            _optional_number(spec, "gap_mm", f"{spec_path}.gap_mm", minimum=0)
            _optional_number(spec, "min_gap_mm", f"{spec_path}.min_gap_mm", minimum=0)
            _optional_number(spec, "impedance_ohm", f"{spec_path}.impedance_ohm", minimum=0)
            _optional_number(spec, "max_skew_ps", f"{spec_path}.max_skew_ps", minimum=0)


def _validate_fabrication(raw: Mapping[str, Any]) -> None:
    _reject_unknown_keys(raw, _FABRICATION_KEYS, "fabrication")
    _optional_number(
        raw,
        "min_trace_width_mm",
        "fabrication.min_trace_width_mm",
        minimum=0.05,
    )
    _optional_number(
        raw,
        "min_clearance_mm",
        "fabrication.min_clearance_mm",
        minimum=0.05,
    )
    _optional_number(raw, "min_drill_mm", "fabrication.min_drill_mm", minimum=0.05)
    _optional_number(
        raw,
        "preferred_via_drill_mm",
        "fabrication.preferred_via_drill_mm",
        minimum=0.05,
    )
    _optional_number(
        raw,
        "soldermask_expansion_mm",
        "fabrication.soldermask_expansion_mm",
        minimum=0,
    )

def _validate_placement_rules(raw: Mapping[str, Any]) -> None:
    _reject_unknown_keys(raw, _PLACEMENT_RULE_KEYS, "placement_rules")
    _optional_bool(raw, "keep_probe_pads_on_grid", "placement_rules.keep_probe_pads_on_grid")
    _optional_bool(raw, "avoid_tall_components", "placement_rules.avoid_tall_components")
    _optional_number(
        raw,
        "min_distance_from_board_edge_mm",
        "placement_rules.min_distance_from_board_edge_mm",
        minimum=0,
    )
    _optional_bool(raw, "group_by_function", "placement_rules.group_by_function")
    if "digital_analog_separation" in raw:
        separation = _require_mapping(
            raw["digital_analog_separation"],
            "placement_rules.digital_analog_separation",
        )
        _reject_unknown_keys(
            separation,
            _DIGITAL_ANALOG_SEPARATION_KEYS,
            "placement_rules.digital_analog_separation",
        )
        _optional_bool(
            separation,
            "enabled",
            "placement_rules.digital_analog_separation.enabled",
        )
        _optional_text(
            separation,
            "split_direction",
            "placement_rules.digital_analog_separation.split_direction",
        )
        _optional_text(
            separation,
            "digital_region",
            "placement_rules.digital_analog_separation.digital_region",
        )
        _optional_text(
            separation,
            "analog_region",
            "placement_rules.digital_analog_separation.analog_region",
        )
        _optional_number(
            separation,
            "isolation_gap_mm",
            "placement_rules.digital_analog_separation.isolation_gap_mm",
            minimum=0,
        )
        _optional_number(
            separation,
            "ground_stitch_via_spacing_mm",
            "placement_rules.digital_analog_separation.ground_stitch_via_spacing_mm",
            minimum=0,
        )


def _validate_development_board(raw: Mapping[str, Any]) -> None:
    _reject_unknown_keys(raw, _DEVELOPMENT_BOARD_KEYS, "development_board")
    _optional_text(raw, "pin_database", "development_board.pin_database")


def _validate_protection(raw: Mapping[str, Any]) -> None:
    _optional_bool(raw, "enabled", "protection.enabled")
    for role, spec in raw.items():
        if role == "enabled":
            continue
        spec_path = f"protection.{role}"
        spec = _require_mapping(spec, spec_path)
        _reject_unknown_keys(spec, _PROTECTION_SPEC_KEYS, spec_path)
        _optional_text(spec, "type", f"{spec_path}.type")
        _optional_text(spec, "value", f"{spec_path}.value")
        _optional_text(spec, "package", f"{spec_path}.package")
        _optional_text(spec, "ref_prefix", f"{spec_path}.ref_prefix")
        _optional_text(spec, "part", f"{spec_path}.part")
        _optional_text(spec, "notes", f"{spec_path}.notes")
        if "stages" in spec:
            stages = _require_list(spec["stages"], f"{spec_path}.stages")
            for index, stage in enumerate(stages):
                stage_path = f"{spec_path}.stages[{index}]"
                stage = _require_mapping(stage, stage_path)
                _reject_unknown_keys(stage, _PROTECTION_SPEC_KEYS, stage_path)


def _validate_impedance_control(raw: Mapping[str, Any]) -> None:
    for name, spec in raw.items():
        spec_path = f"impedance_control.{name}"
        spec = _require_mapping(spec, spec_path)
        _reject_unknown_keys(spec, _IMPEDANCE_RULE_KEYS, spec_path)
        _optional_number(
            spec,
            "target_impedance_ohm",
            f"{spec_path}.target_impedance_ohm",
            minimum=0,
        )
        _optional_number(spec, "tolerance_percent", f"{spec_path}.tolerance_percent", minimum=0)
        _optional_number(spec, "diff_pair_width_mm", f"{spec_path}.diff_pair_width_mm", minimum=0)
        _optional_number(spec, "diff_pair_gap_mm", f"{spec_path}.diff_pair_gap_mm", minimum=0)


def _validate_thermal_analysis(raw: Mapping[str, Any]) -> None:
    _reject_unknown_keys(raw, _THERMAL_ANALYSIS_KEYS, "thermal_analysis")
    _optional_bool(raw, "enabled", "thermal_analysis.enabled")
    _optional_number(raw, "max_junction_temp_c", "thermal_analysis.max_junction_temp_c")
    _optional_number(raw, "ambient_temp_c", "thermal_analysis.ambient_temp_c")
    _optional_text(raw, "output_format", "thermal_analysis.output_format")


def _validate_resource_allocator(raw: Mapping[str, Any]) -> None:
    _reject_unknown_keys(raw, _RESOURCE_ALLOCATOR_KEYS, "resource_allocator")
    _optional_bool(raw, "enable", "resource_allocator.enable")
    _optional_text(raw, "bus_allocation_strategy", "resource_allocator.bus_allocation_strategy")
    _optional_text(raw, "power_allocation_strategy", "resource_allocator.power_allocation_strategy")
    _optional_text(
        raw,
        "connector_allocation_strategy",
        "resource_allocator.connector_allocation_strategy",
    )
    _optional_bool(raw, "allow_partial_allocation", "resource_allocator.allow_partial_allocation")
    _optional_number(
        raw,
        "near_limit_threshold",
        "resource_allocator.near_limit_threshold",
        minimum=0,
    )
    _optional_bool(raw, "overload_block", "resource_allocator.overload_block")


def _validate_process_controls(
    raw: Mapping[str, Any],
    legacy_waivers: list[Any],
) -> None:
    _reject_unknown_keys(raw, _PROCESS_CONTROL_KEYS, "process_controls")
    _optional_bool(raw, "strict_signoff", "process_controls.strict_signoff")
    _optional_bool(
        raw,
        "require_autorouter_feedback",
        "process_controls.require_autorouter_feedback",
    )
    _optional_bool(
        raw,
        "require_manufacturing_exports",
        "process_controls.require_manufacturing_exports",
    )
    _optional_int(
        raw,
        "scalability_module_warning_threshold",
        "process_controls.scalability_module_warning_threshold",
        minimum=0,
    )
    _optional_int(
        raw,
        "scalability_net_warning_threshold",
        "process_controls.scalability_net_warning_threshold",
        minimum=0,
    )
    waivers = _require_list(raw.get("waivers", legacy_waivers), "process_controls.waivers")
    _validate_process_waivers(waivers, "process_controls.waivers")
    if "params" in raw:
        _require_mapping(raw["params"], "process_controls.params")


def _validate_process_waivers(rows: list[Any], path: str) -> None:
    for index, row in enumerate(rows):
        row_path = f"{path}[{index}]"
        row = _require_mapping(row, row_path)
        _reject_unknown_keys(row, _PROCESS_WAIVER_KEYS, row_path)
        _optional_text(row, "id", f"{row_path}.id")
        _optional_text(row, "waiver_id", f"{row_path}.waiver_id")
        _optional_text(row, "source", f"{row_path}.source")
        _optional_text(row, "issue_id", f"{row_path}.issue_id")
        _optional_text(row, "reason", f"{row_path}.reason")
        _optional_text(row, "owner", f"{row_path}.owner")
        _optional_text(row, "approved_by", f"{row_path}.approved_by")
        _optional_text(row, "expires_on", f"{row_path}.expires_on")
        _optional_text(row, "expires", f"{row_path}.expires")


def _validate_module_footprint_preview(raw: Mapping[str, Any]) -> None:
    _reject_unknown_keys(raw, _MODULE_FOOTPRINT_PREVIEW_KEYS, "module_footprint_preview")
    _optional_bool(raw, "enable", "module_footprint_preview.enable")
    _optional_bool(raw, "enabled", "module_footprint_preview.enabled")
    _optional_text(raw, "mode", "module_footprint_preview.mode")
    if raw.get("mode", "preview") not in {"preview", "emit_candidate"}:
        raise ConfigValidationError(
            "module_footprint_preview.mode must be 'preview' or 'emit_candidate'"
        )
    _optional_bool(raw, "write_candidate_pcb", "module_footprint_preview.write_candidate_pcb")
    _optional_bool(raw, "block_on_collision", "module_footprint_preview.block_on_collision")
    _optional_bool(
        raw,
        "block_on_missing_footprint",
        "module_footprint_preview.block_on_missing_footprint",
    )
    _optional_bool(
        raw,
        "block_on_keepout_violation",
        "module_footprint_preview.block_on_keepout_violation",
    )
    _optional_text(raw, "candidate_suffix", "module_footprint_preview.candidate_suffix")


def _validate_plugin_shell(raw: Mapping[str, Any]) -> None:
    _reject_unknown_keys(raw, _PLUGIN_SHELL_KEYS, "plugin_shell")
    _optional_text(raw, "step_file", "plugin_shell.step_file")
    _optional_bool(raw, "enable_3d", "plugin_shell.enable_3d")
    _optional_bool(raw, "fallback_to_2d_board", "plugin_shell.fallback_to_2d_board")


def _validate_crystal(raw: Mapping[str, Any]) -> None:
    _reject_unknown_keys(raw, _CRYSTAL_KEYS, "crystal")
    _optional_number(raw, "frequency_mhz", "crystal.frequency_mhz", minimum=0)
    _optional_text(raw, "type", "crystal.type")
    _optional_text(raw, "package", "crystal.package")
    _optional_number(raw, "tolerance_ppm", "crystal.tolerance_ppm", minimum=0)
    _optional_text(raw, "notes", "crystal.notes")


def _optional_bool(raw: Mapping[str, Any], key: str, path: str) -> None:
    if key in raw and not isinstance(raw[key], bool):
        raise ConfigValidationError(f"{path} must be a boolean")


def _reject_unknown_keys(
    raw: Mapping[str, Any],
    allowed: set[str],
    path: str,
) -> None:
    unknown = sorted(str(key) for key in raw if str(key) not in allowed)
    if not unknown:
        return
    prefix = f"{path}." if path else ""
    keys = ", ".join(f"{prefix}{key}" for key in unknown)
    raise ConfigValidationError(f"Unsupported config key: {keys}")


def _optional_int(
    raw: Mapping[str, Any],
    key: str,
    path: str,
    minimum: int | None = None,
) -> None:
    if key not in raw:
        return
    value = _coerce_int(raw[key], path)
    if minimum is not None and value < minimum:
        raise ConfigValidationError(f"{path} must be >= {minimum}")


def _optional_number(
    raw: Mapping[str, Any],
    key: str,
    path: str,
    minimum: float | None = None,
) -> None:
    if key not in raw:
        return
    value = _coerce_float(raw[key], path)
    if minimum is not None and value < minimum:
        raise ConfigValidationError(f"{path} must be >= {minimum}")


def _optional_text(raw: Mapping[str, Any], key: str, path: str) -> None:
    if key in raw:
        _require_text(raw[key], path)


def _optional_text_list(raw: Mapping[str, Any], key: str, path: str) -> None:
    if key not in raw:
        return
    values = _require_list(raw[key], path)
    for index, value in enumerate(values):
        _require_text(value, f"{path}[{index}]")


def _require_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigValidationError(f"{path} must be a YAML mapping")
    return value


def _require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ConfigValidationError(f"{path} must be a YAML list")
    return value


def _require_text(value: Any, path: str) -> str:
    if isinstance(value, bool) or not isinstance(value, _TEXT_TYPES):
        raise ConfigValidationError(f"{path} must be a string")
    return str(value)


def _require_non_empty_text(value: Any, path: str) -> str:
    if value is None:
        raise ConfigValidationError(f"{path} is required")
    text = _require_text(value, path)
    if not text.strip():
        raise ConfigValidationError(f"{path} is required")
    return text


def _coerce_int(value: Any, path: str) -> int:
    if isinstance(value, bool):
        raise ConfigValidationError(f"{path} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        raise ConfigValidationError(f"{path} must be an integer")
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise ConfigValidationError(f"{path} must be an integer") from exc
    raise ConfigValidationError(f"{path} must be an integer")


def _coerce_float(value: Any, path: str) -> float:
    if isinstance(value, bool):
        raise ConfigValidationError(f"{path} must be a number")
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError as exc:
            raise ConfigValidationError(f"{path} must be a number") from exc
    raise ConfigValidationError(f"{path} must be a number")


def _type_name(expected_type: type | tuple[type, ...]) -> str:
    if isinstance(expected_type, tuple):
        return " or ".join(_type_name(t) for t in expected_type)
    if expected_type is dict:
        return "a YAML mapping"
    if expected_type is list:
        return "a YAML list"
    if expected_type is bool:
        return "a boolean"
    return expected_type.__name__
