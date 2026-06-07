"""Version and supply-flexibility metadata for planned modules."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModuleCompatibilityRow:
    module_id: str
    module_name: str
    module_type: str
    module_version: str = ""
    requested_version: str = ""
    definition_version: str = ""
    implementation: str = ""
    implementation_version: str = ""
    component_role: str = ""
    component_type: str = ""
    component_version: str = ""
    chip: str = ""
    chip_version: str = ""
    package_options: list[str] = field(default_factory=list)
    footprint_version: str = ""
    alternate_chips: list[str] = field(default_factory=list)
    alternate_footprints: list[str] = field(default_factory=list)
    status: str = "ok"
    notes: list[str] = field(default_factory=list)


@dataclass
class ModuleCompatibilityResult:
    rows: list[ModuleCompatibilityRow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors
