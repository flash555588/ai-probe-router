"""Deterministic run-id fingerprinting for engine runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..config import ProjectConfig


def build_run_id(cfg: ProjectConfig, base: Path) -> str:
    """Derive a stable run id from the config and input file fingerprints."""
    payload = {
        "schema_version": cfg.schema_version,
        "board": _project_file_fingerprint(base, cfg.board_file),
        "schematic": _project_file_fingerprint(base, cfg.schematic_file),
        "design_goals": {
            "optimize_for": cfg.design_goals.optimize_for,
            "max_added_area_mm2": cfg.design_goals.max_added_area_mm2,
            "preferred_side": cfg.design_goals.preferred_side,
            "human_review_required_for": cfg.design_goals.human_review_required_for,
        },
        "hardware_platform": {
            "target_voltage_domains": [
                {
                    "name": domain.name,
                    "voltage": domain.voltage,
                    "max_current_ma": domain.max_current_ma,
                }
                for domain in cfg.hardware_platform.target_voltage_domains
            ],
        },
        "module_placement": {
            "group_by_module": cfg.module_placement.group_by_module,
            "keep_power_modules_near_input": cfg.module_placement.keep_power_modules_near_input,
            "keep_analog_modules_away_from_switching_power": (
                cfg.module_placement.keep_analog_modules_away_from_switching_power
            ),
            "keep_debug_near_board_edge": cfg.module_placement.keep_debug_near_board_edge,
            "max_module_to_probe_distance_mm": (
                cfg.module_placement.max_module_to_probe_distance_mm
            ),
        },
        "routing_strategy": {
            "coarse_grid_mm": cfg.routing_strategy.coarse_grid_mm,
            "max_corridor_layers": cfg.routing_strategy.max_corridor_layers,
            "congestion_weight": cfg.routing_strategy.congestion_weight,
            "via_weight": cfg.routing_strategy.via_weight,
            "length_weight": cfg.routing_strategy.length_weight,
            "sensitive_net_spacing_mm": cfg.routing_strategy.sensitive_net_spacing_mm,
        },
        "probe": {
            "style": cfg.probe.style.name,
            "side": cfg.probe.side,
            "pad_diameter_mm": cfg.probe.pad_diameter_mm,
            "min_spacing_mm": cfg.probe.min_spacing_mm,
            "preferred_grid_mm": cfg.probe.preferred_grid_mm,
            "require_silkscreen_labels": cfg.probe.require_silkscreen_labels,
            "require_fiducials": cfg.probe.require_fiducials,
            "require_tooling_holes": cfg.probe.require_tooling_holes,
        },
        "constraints": {
            "routing": {
                "default_trace_width_mm": cfg.constraints.routing.default_trace_width_mm,
                "power_trace_width_mm": cfg.constraints.routing.power_trace_width_mm,
                "min_clearance_mm": cfg.constraints.routing.min_clearance_mm,
                "max_vias_per_signal": cfg.constraints.routing.max_vias_per_signal,
                "avoid_under_components": cfg.constraints.routing.avoid_under_components,
            },
            "placement": {
                "keep_probe_pads_on_grid": cfg.constraints.placement.keep_probe_pads_on_grid,
                "avoid_tall_components": cfg.constraints.placement.avoid_tall_components,
                "min_distance_from_board_edge_mm": (
                    cfg.constraints.placement.min_distance_from_board_edge_mm
                ),
                "group_by_function": cfg.constraints.placement.group_by_function,
            },
        },
        "process_controls": {
            "strict_signoff": cfg.process_controls.strict_signoff,
            "require_autorouter_feedback": (
                cfg.process_controls.require_autorouter_feedback
            ),
            "require_manufacturing_exports": (
                cfg.process_controls.require_manufacturing_exports
            ),
            "scalability_module_warning_threshold": (
                cfg.process_controls.scalability_module_warning_threshold
            ),
            "scalability_net_warning_threshold": (
                cfg.process_controls.scalability_net_warning_threshold
            ),
            "waivers": [
                {
                    "waiver_id": waiver.waiver_id,
                    "source": waiver.source,
                    "issue_id": waiver.issue_id,
                    "owner": waiver.owner,
                    "reason": waiver.reason,
                    "expires_on": waiver.expires_on,
                }
                for waiver in cfg.process_controls.waivers
            ],
            "params": _json_safe(cfg.process_controls.params),
        },
        "nets": [
            {
                "net": req.net_name,
                "role": str(req.role),
                "required": req.required,
                "pair": req.pair_net_name,
                "duplicates": req.duplicate_probe_count,
                "current_ma": req.current_ma,
                "preferred_devboard_pins": req.preferred_devboard_pins,
            }
            for req in cfg.nets_to_expose
        ],
        "modules": [
            {
                "name": module.name,
                "type": module.type,
                "required": module.required,
                "version": module.version,
                "target_nets": module.target_nets,
                "depends_on": module.depends_on,
                "channels": module.channels,
                "voltage_domains": module.voltage_domains,
                "allowed_implementations": module.allowed_implementations,
                "allowed_interfaces": module.allowed_interfaces,
                "rails": module.rails,
                "telemetry_bus": module.telemetry_bus,
                "resolution_bits_min": module.resolution_bits_min,
                "budget_area_mm2": module.budget_area_mm2,
                "preferred_region": module.preferred_region,
                "ai_hints": [
                    {
                        "type": hint.hint_type,
                        "target": hint.target,
                        "value": hint.value,
                        "params": _json_safe(hint.params),
                        "ignored_reason": hint.ignored_reason,
                    }
                    for hint in module.ai_hints
                ],
                "require_level_shift": module.require_level_shift,
                "require_esd": module.require_esd,
                "require_input_protection": module.require_input_protection,
                "require_mux": module.require_mux,
                "params": _json_safe(module.params),
            }
            for module in cfg.functional_modules
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha1(encoded.encode("utf-8")).hexdigest()[:12].upper()
    return f"APR-{digest}"


def _project_file_fingerprint(base: Path, value: str) -> dict[str, object]:
    if not value:
        return {"path": "", "exists": False}
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    normalized = value.replace("\\", "/")
    if not path.is_file():
        return {"path": normalized, "exists": False}
    data = path.read_bytes()
    return {
        "path": normalized,
        "exists": True,
        "size_bytes": len(data),
        "sha1": hashlib.sha1(data).hexdigest(),
    }


def _json_safe(value: object) -> object:
    try:
        json.dumps(value, sort_keys=True)
    except TypeError:
        return repr(value)
    return value
