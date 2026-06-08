"""Generate a per-module CSV BOM report."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from ..models.module_graph import ModuleGraphResult


@dataclass
class BomReport:
    result: ModuleGraphResult
    run_id: str = ""

    def write(self, path: str | Path) -> None:
        with Path(path).open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "run_id",
                "module_id",
                "module_name",
                "module_type",
                "module_version",
                "requested_module_version",
                "definition_version",
                "implementation",
                "implementation_version",
                "component_role",
                "component_type",
                "component_version",
                "chip",
                "chip_version",
                "count",
                "package_options",
                "footprint_version",
                "alternate_chips",
                "alternate_footprints",
                "value_options",
            ])
            for instance in self.result.graph.instances:
                for component in instance.components:
                    writer.writerow([
                        self.run_id,
                        instance.instance_id,
                        instance.name,
                        instance.module_type,
                        instance.version,
                        instance.requested_version,
                        instance.selected_definition_version,
                        instance.selected_implementation,
                        instance.selected_implementation_version,
                        component.role,
                        component.type,
                        component.version,
                        component.chip,
                        component.chip_version,
                        component.count,
                        "|".join(component.package_options),
                        component.footprint_version,
                        "|".join(component.alternate_chips),
                        "|".join(component.alternate_footprints),
                        "|".join(component.value_options),
                    ])
