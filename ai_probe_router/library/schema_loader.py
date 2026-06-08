"""Load JSON schemas for library validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SchemaLoader:
    """Loads JSON schemas from the schemas/ directory."""

    _SCHEMA_NAMES = {
        "chip": "chip_definition.schema.json",
        "module": "module_definition.schema.json",
        "dev_board": "dev_board.schema.json",
        "project_config": "project_config.schema.json",
    }

    def __init__(self, schema_dir: str | Path | None = None) -> None:
        if schema_dir is None:
            # Schemas live next to the package root
            here = Path(__file__).resolve().parent.parent.parent
            schema_dir = here / "schemas"
        self.schema_dir = Path(schema_dir)
        self._cache: dict[str, dict[str, Any]] = {}

    def load(self, name: str) -> dict[str, Any]:
        """Load a schema by logical name (chip, module, dev_board, project_config)."""
        if name in self._cache:
            return self._cache[name]
        filename = self._SCHEMA_NAMES.get(name)
        if filename is None:
            raise KeyError(f"Unknown schema: {name}")
        path = self.schema_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Schema file not found: {path}")
        with path.open("r", encoding="utf-8") as f:
            schema = json.load(f)
        self._cache[name] = schema
        return schema

    def all_schemas(self) -> dict[str, dict[str, Any]]:
        """Load all known schemas."""
        return {name: self.load(name) for name in self._SCHEMA_NAMES}
