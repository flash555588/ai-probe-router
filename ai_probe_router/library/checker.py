"""Library validation with three layers: JSON schema, semantic, compatibility."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .schema_loader import SchemaLoader


class ValidationSeverity(enum.Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    severity: ValidationSeverity
    layer: str
    file: Path
    message: str
    field: str = ""


class LibraryChecker:
    """Validate chip, module, dev-board, and project-config libraries."""

    def __init__(
        self,
        library_root: str | Path,
        schema_loader: SchemaLoader | None = None,
        strict: bool = False,
        include_experimental: bool = True,
    ) -> None:
        self.library_root = Path(library_root)
        self.schema_loader = schema_loader or SchemaLoader()
        self.strict = strict
        self.include_experimental = include_experimental
        self.issues: list[ValidationIssue] = []
        self._jsonschema: Any = None

    def check_all(self) -> list[ValidationIssue]:
        """Run all validation layers on the library tree."""
        self.issues = []
        self._check_json_schema_layer()
        self._check_semantic_layer()
        self._check_compatibility_layer()
        return self.issues

    def _check_json_schema_layer(self) -> None:
        """Layer 1: Validate YAML files against JSON schemas."""
        schema_map = {
            "chip": ("chips", "chip"),
            "module": ("modules", "module"),
            "dev_board": ("dev_boards", "dev_board"),
        }
        for kind, (rel_dir, schema_name) in schema_map.items():
            schema = self.schema_loader.load(schema_name)
            base = self.library_root / rel_dir
            if not base.exists():
                self.issues.append(
                    ValidationIssue(
                        ValidationSeverity.WARNING,
                        "json_schema",
                        base,
                        f"Directory missing: {rel_dir}",
                    )
                )
                continue
            for path in sorted(base.rglob("*.yaml")):
                self._validate_yaml_against_schema(path, schema, kind)

    def _validate_yaml_against_schema(
        self, path: Path, schema: dict[str, Any], kind: str
    ) -> None:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            self.issues.append(
                ValidationIssue(
                    ValidationSeverity.ERROR,
                    "json_schema",
                    path,
                    f"Invalid YAML: {exc}",
                )
            )
            return

        if data is None:
            self.issues.append(
                ValidationIssue(
                    ValidationSeverity.ERROR,
                    "json_schema",
                    path,
                    "Empty YAML file",
                )
            )
            return

        validator = self._get_jsonschema_validator(schema)
        errors = list(validator.iter_errors(data))
        for err in errors:
            field_path = "/".join(str(p) for p in err.absolute_path)
            self.issues.append(
                ValidationIssue(
                    ValidationSeverity.ERROR if self.strict else ValidationSeverity.WARNING,
                    "json_schema",
                    path,
                    f"[{kind}] {err.message}",
                    field=field_path,
                )
            )

    def _check_semantic_layer(self) -> None:
        """Layer 2: Validate meaning and constraints."""
        chips = self._load_all("chips")
        modules = self._load_all("modules")
        boards = self._load_all("dev_boards")

        self._validate_chip_semantics(chips)
        self._validate_module_semantics(modules, chips)
        self._validate_dev_board_semantics(boards)

    def _validate_chip_semantics(
        self, chips: dict[Path, dict[str, Any]]
    ) -> None:
        for path, data in chips.items():
            _chip = data.get("chip", {})
            pins = data.get("pins", [])
            interfaces = data.get("interfaces", [])
            power = data.get("power", {})
            domains = power.get("domains", [])
            domain_names = {d["name"] for d in domains}

            for pin in pins:
                vdomain = pin.get("voltage_domain")
                if vdomain and vdomain not in domain_names:
                    self.issues.append(
                        ValidationIssue(
                            ValidationSeverity.WARNING,
                            "semantic",
                            path,
                            f"Pin '{pin.get('name')}' references voltage "
                            f"domain '{vdomain}' not in power domains",
                            field="pins/voltage_domain",
                        )
                    )

            for iface in interfaces:
                for pin_name in iface.get("pins", []):
                    pin_names = {p["name"] for p in pins}
                    if pin_name not in pin_names:
                        self.issues.append(
                            ValidationIssue(
                                ValidationSeverity.WARNING,
                                "semantic",
                                path,
                            f"Interface '{iface.get('type')}' references pin "
                            f"'{pin_name}' not in pins list",
                                field="interfaces/pins",
                            )
                        )

            for domain in domains:
                if domain.get("current_max_ma", 0) < 0:
                    self.issues.append(
                        ValidationIssue(
                            ValidationSeverity.ERROR,
                            "semantic",
                            path,
                            f"Negative current_max_ma in domain '{domain['name']}'",
                            field="power/domains/current_max_ma",
                        )
                    )

    def _validate_module_semantics(
        self,
        modules: dict[Path, dict[str, Any]],
        chips: dict[Path, dict[str, Any]],
    ) -> None:
        chip_mpns = set()
        for data in chips.values():
            mpn = data.get("chip", {}).get("mpn")
            if mpn:
                chip_mpns.add(mpn)

        for path, data in modules.items():
            module_meta = data.get("module", {})
            lifecycle = module_meta.get("lifecycle", "stable")
            if lifecycle == "experimental" and not self.include_experimental:
                self.issues.append(
                    ValidationIssue(
                        ValidationSeverity.INFO,
                        "semantic",
                        path,
                        "Experimental module skipped from compatibility checks",
                    )
                )
                continue

            implementations = data.get("implementations", [])
            for impl in implementations:
                for comp in impl.get("components", []):
                    chip = comp.get("chip")
                    if chip and chip not in chip_mpns:
                        self.issues.append(
                            ValidationIssue(
                                ValidationSeverity.WARNING,
                                "semantic",
                                path,
                                f"Component references unknown chip '{chip}'",
                                field="implementations/components/chip",
                            )
                        )

                constraints = impl.get("constraints", {})
                i2c_addr = constraints.get("i2c_address")
                if i2c_addr is not None:
                    try:
                        addr = int(str(i2c_addr), 0)
                        if not (0x08 <= addr <= 0x77):
                            self.issues.append(
                                ValidationIssue(
                                    ValidationSeverity.WARNING,
                                    "semantic",
                                    path,
                                    f"I2C address {hex(addr)} outside valid range 0x08-0x77",
                                    field="constraints/i2c_address",
                                )
                            )
                    except ValueError:
                        self.issues.append(
                            ValidationIssue(
                                ValidationSeverity.WARNING,
                                "semantic",
                                path,
                                f"Invalid I2C address '{i2c_addr}'",
                                field="constraints/i2c_address",
                            )
                        )

    def _validate_dev_board_semantics(
        self, boards: dict[Path, dict[str, Any]]
    ) -> None:
        for path, data in boards.items():
            pins = data.get("pins", [])
            for pin in pins:
                caps = set(pin.get("capabilities", []))
                is_power = pin.get("is_power", False)
                is_ground = pin.get("is_ground", False)
                if is_power and "GND" in caps:
                    self.issues.append(
                        ValidationIssue(
                            ValidationSeverity.WARNING,
                            "semantic",
                            path,
                            f"Pin '{pin['name']}' marked is_power but has GND capability",
                            field="pins",
                        )
                    )
                if is_ground and not caps.intersection({"GND", "GROUND"}):
                    self.issues.append(
                        ValidationIssue(
                            ValidationSeverity.WARNING,
                            "semantic",
                            path,
                            f"Pin '{pin['name']}' marked is_ground but lacks GND capability",
                            field="pins",
                        )
                    )

    def _check_compatibility_layer(self) -> None:
        """Layer 3: Cross-reference validation."""
        chips = self._load_all("chips")
        modules = self._load_all("modules")

        chip_mpns = {}
        for path, data in chips.items():
            mpn = data.get("chip", {}).get("mpn")
            if mpn:
                chip_mpns[mpn] = path

        for path, data in modules.items():
            implementations = data.get("implementations", [])
            for impl in implementations:
                for comp in impl.get("components", []):
                    chip_name = comp.get("chip")
                    if chip_name and chip_name in chip_mpns:
                        pkg_options = comp.get("package_options", [])
                        chip_data = chips[chip_mpns[chip_name]]
                        chip_pkgs = {p["name"] for p in chip_data.get("package_options", [])}
                        for pkg in pkg_options:
                            if chip_pkgs and pkg not in chip_pkgs:
                                self.issues.append(
                                    ValidationIssue(
                                        ValidationSeverity.WARNING,
                                        "compatibility",
                                        path,
                                        f"Package '{pkg}' not declared on chip '{chip_name}'",
                                        field="components/package_options",
                                    )
                                )

    def _load_all(self, rel_dir: str) -> dict[Path, dict[str, Any]]:
        base = self.library_root / rel_dir
        result: dict[Path, dict[str, Any]] = {}
        if not base.exists():
            return result
        for path in sorted(base.rglob("*.yaml")):
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if data is not None:
                    result[path] = data
            except yaml.YAMLError:
                pass
        return result

    def _get_jsonschema_validator(self, schema: dict[str, Any]):
        if self._jsonschema is None:
            try:
                import jsonschema

                self._jsonschema = jsonschema
            except ImportError as exc:
                raise RuntimeError("jsonschema is required for schema validation") from exc
        return self._jsonschema.Draft7Validator(schema)
