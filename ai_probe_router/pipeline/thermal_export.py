"""Thermal analysis export (CSV/JSON) for engine runs."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from ..config import ProjectConfig
from ..models.board import Board

_THERMAL_FIELDS = [
    "ref",
    "pad",
    "x",
    "y",
    "net_name",
    "role",
    "current_ma",
    "voltage_v",
    "estimated_power_mw",
    "risk",
]


def write_thermal_analysis_export(
    board: Board,
    cfg: ProjectConfig,
    out_dir: Path,
) -> Path:
    output_format = cfg.thermal_analysis.output_format.lower().lstrip(".")
    if output_format not in {"csv", "json"}:
        output_format = "csv"
    rows = _thermal_export_rows(board, cfg)
    path = out_dir / f"thermal_simulation.{output_format}"
    if output_format == "json":
        payload = {
            "thermal_analysis": cfg.thermal_analysis.to_dict(),
            "rows": rows,
        }
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_THERMAL_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    return path


def _thermal_export_rows(
    board: Board,
    cfg: ProjectConfig,
) -> list[dict[str, object]]:
    reqs_by_net = {req.net_name: req for req in cfg.nets_to_expose}
    rows: list[dict[str, object]] = []
    for fp in board.footprints:
        for pad in fp.pads:
            req = reqs_by_net.get(pad.net_name)
            current_ma = float(req.current_ma) if req is not None else 0.0
            voltage_v = _thermal_voltage_for_net(pad.net_name, cfg)
            estimated_power_mw = current_ma * voltage_v
            rows.append({
                "ref": fp.ref,
                "pad": pad.number,
                "x": round(pad.x, 3),
                "y": round(pad.y, 3),
                "net_name": pad.net_name,
                "role": str(req.role) if req is not None else "",
                "current_ma": round(current_ma, 3),
                "voltage_v": round(voltage_v, 3),
                "estimated_power_mw": round(estimated_power_mw, 3),
                "risk": _thermal_risk(current_ma, estimated_power_mw),
            })
    return rows


def _thermal_voltage_for_net(net_name: str, cfg: ProjectConfig) -> float:
    domains = cfg.hardware_platform.target_voltage_domains
    if not domains:
        return 3.3
    normalized_net = net_name.lower()
    for domain in domains:
        normalized_domain = domain.name.lower()
        if normalized_domain and (
            normalized_domain == normalized_net
            or normalized_domain in normalized_net
        ):
            return domain.voltage
    return domains[0].voltage


def _thermal_risk(current_ma: float, estimated_power_mw: float) -> str:
    if current_ma >= 1000.0 or estimated_power_mw >= 1000.0:
        return "high"
    if current_ma >= 200.0 or estimated_power_mw >= 500.0:
        return "medium"
    return "low"
