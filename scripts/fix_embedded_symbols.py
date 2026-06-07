#!/usr/bin/env python3
"""Replace embedded symbol definitions in KiCad schematic with library references.

KiCad schematics can embed symbol definitions directly in lib_symbols section
instead of referencing external libraries. This script:
1. Identifies embedded symbols that have matching library equivalents
2. Removes the embedded definition from lib_symbols
3. Keeps the instance (symbol placement) unchanged - it already references the lib

The instance's lib_id already points to the library (e.g., "RF_Module:ESP32-S3-WROOM-1"),
so only the embedded definition in lib_symbols needs to be removed.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_probe_router.eda_adapters.kicad.sexpr import parse, serialize


def is_embedded_symbol(sym_def: list) -> bool:
    """Check if a symbol definition in lib_symbols is embedded (not a library ref).

    In KiCad, lib_symbols entries look like:
      (symbol "LibName:SymbolName" ...)  -> library reference
      (symbol "SymbolName" ...)          -> embedded definition

    But actually both can have colons. The real distinction is:
    - Library references are just (symbol "Lib:Name" (property ...) (pin ...))
    - Embedded definitions have sub-symbol units like "Name_0_1", "Name_1_1"

    A simpler heuristic: if the symbol name contains a colon, it's a library reference.
    If not, it's an embedded definition.
    """
    if not sym_def or not isinstance(sym_def[0], str) or sym_def[0] != "symbol":
        return False
    if len(sym_def) < 2:
        return False
    name = sym_def[1]
    if isinstance(name, list):
        name = name[0] if name else ""
    return ":" not in str(name)


def get_symbol_name(sym_def: list) -> str:
    """Extract the symbol name from a lib_symbols entry."""
    if len(sym_def) < 2:
        return ""
    name = sym_def[1]
    if isinstance(name, list):
        name = name[0] if name else ""
    return str(name)


def find_matching_lib_symbol(sym_def: list, lib_symbols: list) -> str | None:
    """Find if there's a library symbol that matches this embedded definition.

    Returns the library-qualified name (e.g., "RF_Module:ESP32-S3-WROOM-1") or None.
    """
    embedded_name = get_symbol_name(sym_def)

    for lib_sym in lib_symbols:
        if not isinstance(lib_sym, list) or len(lib_sym) < 2:
            continue
        if lib_sym[0] != "symbol":
            continue
        lib_name = str(lib_sym[1]) if not isinstance(lib_sym[1], list) else str(lib_sym[1][0])
        if ":" in lib_name:
            # Extract the short name after the colon
            short_name = lib_name.split(":", 1)[1]
            if short_name == embedded_name:
                return lib_name
    return None


def fix_schematic(sch_path: Path, dry_run: bool = False) -> list[str]:
    """Fix embedded symbols in a KiCad schematic file.

    Returns a list of actions taken.
    """
    text = sch_path.read_text(encoding="utf-8")
    tree = parse(text)

    if not isinstance(tree, list) or tree[0] != "kicad_sch":
        raise ValueError(f"Not a valid KiCad schematic: {sch_path}")

    actions: list[str] = []

    # Find lib_symbols section
    lib_symbols_idx = None
    lib_symbols = None
    for i, child in enumerate(tree):
        if isinstance(child, list) and child and child[0] == "lib_symbols":
            lib_symbols_idx = i
            lib_symbols = child
            break

    if lib_symbols_idx is None:
        actions.append("No lib_symbols section found")
        return actions

    # Collect all symbol definitions in lib_symbols
    sym_defs: list[list] = []
    for child in lib_symbols[1:]:  # Skip "lib_symbols" tag
        if isinstance(child, list) and child and child[0] == "symbol":
            sym_defs.append(child)

    # Find embedded symbols that have library equivalents
    to_remove: list[tuple[int, str, str]] = []  # (index in lib_symbols, embedded_name, lib_name)

    for sym_def in sym_defs:
        name = get_symbol_name(sym_def)
        if ":" not in name:
            # This is an embedded symbol, check if there's a library equivalent
            lib_name = find_matching_lib_symbol(sym_def, sym_defs)
            if lib_name:
                # Find its index in lib_symbols
                for idx, child in enumerate(lib_symbols):
                    if child is sym_def:
                        to_remove.append((idx, name, lib_name))
                        break

    if not to_remove:
        actions.append("No embedded symbols with library equivalents found")
        return actions

    # Remove embedded symbols (in reverse order to preserve indices)
    for idx, embedded_name, lib_name in sorted(to_remove, key=lambda x: x[0], reverse=True):
        actions.append(f"Removed embedded '{embedded_name}' -> use library '{lib_name}'")
        lib_symbols.pop(idx)

    if not dry_run:
        # Backup original
        backup = sch_path.with_suffix(sch_path.suffix + ".bak")
        shutil.copy2(sch_path, backup)

        # Write fixed file
        fixed_text = serialize(tree)
        sch_path.write_text(fixed_text, encoding="utf-8")
        actions.append(f"Backup saved to: {backup}")
        actions.append(f"Fixed file written to: {sch_path}")
    else:
        actions.append("(dry-run: no changes written)")

    return actions


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replace embedded KiCad schematic symbols with library references"
    )
    parser.add_argument("sch_file", help="Path to .kicad_sch file")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without modifying")
    args = parser.parse_args()

    sch_path = Path(args.sch_file)
    if not sch_path.exists():
        print(f"Error: File not found: {sch_path}", file=sys.stderr)
        return 1

    try:
        actions = fix_schematic(sch_path, dry_run=args.dry_run)
        for action in actions:
            print(action)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
