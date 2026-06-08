"""Minimal s-expression parser/serializer for KiCad file formats.

KiCad uses s-expressions for .kicad_sch, .kicad_pcb, .kicad_sym, and .kicad_mod.
This module handles tokenizing, parsing into nested Python lists, and serializing back.
"""

from __future__ import annotations


class QuotedStr(str):
    """A string that was originally quoted in the source file."""


SExpr = str | list["SExpr"]


def parse(text: str) -> SExpr:
    tokens = _tokenize(text)
    expr, pos = _read(tokens, 0)
    return expr


def serialize(expr: SExpr, indent: int = 0) -> str:
    if isinstance(expr, str):
        if isinstance(expr, QuotedStr) or _needs_quoting(expr):
            return '"' + expr.replace("\\", "\\\\").replace('"', '\\"') + '"'
        return expr
    parts: list[str] = []
    if not expr:
        return "()"
    tag = expr[0] if isinstance(expr[0], str) else None
    compact = tag in _COMPACT_TAGS or all(isinstance(e, str) for e in expr)
    if compact:
        inner = " ".join(serialize(e, 0) for e in expr)
        return f"({inner})"
    prefix = "  " * indent
    child_prefix = "  " * (indent + 1)
    parts.append(f"({serialize(expr[0], 0)}")
    for child in expr[1:]:
        if isinstance(child, str):
            parts[-1] += " " + serialize(child, 0)
        else:
            parts.append(child_prefix + serialize(child, indent + 1))
    parts.append(prefix + ")")
    return "\n".join(parts)


_COMPACT_TAGS = frozenset({
    "at", "xy", "pts", "size", "width", "height", "start", "end", "mid",
    "stroke", "effects", "font", "justify", "offset", "rect_delta",
    "drill", "net", "layers", "layer", "tstamp", "uuid", "version",
    "generator", "generator_version", "paper", "thickness", "angle",
    "thermal_gap", "thermal_bridge_width", "clearance", "die_length",
    "solder_mask_margin", "solder_paste_margin", "solder_paste_ratio",
    "roundrect_rratio", "chamfer_ratio",
})


def _needs_quoting(s: str) -> bool:
    if not s:
        return True
    if _looks_like_uuid(s):
        return False
    # Numbers (int/float/negative) don't need quoting
    try:
        float(s)
        return False
    except ValueError:
        pass
    # Lowercase keywords (letters, digits, underscores) don't need quoting
    if s[0].islower() and all(c.islower() or c.isdigit() or c == '_' for c in s):
        return False
    # Everything else needs quoting (uppercase, dots, colons, hyphens, etc.)
    return True


def _looks_like_uuid(s: str) -> bool:
    parts = s.split("-")
    if [len(p) for p in parts] != [8, 4, 4, 4, 12]:
        return False
    return all(part and all(c in "0123456789abcdefABCDEF" for c in part) for part in parts)


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in " \t\n\r":
            i += 1
        elif c == "(":
            tokens.append("(")
            i += 1
        elif c == ")":
            tokens.append(")")
            i += 1
        elif c == '"':
            j = i + 1
            buf: list[str] = []
            while j < n:
                if text[j] == "\\" and j + 1 < n:
                    buf.append(text[j + 1])
                    j += 2
                elif text[j] == '"':
                    j += 1
                    break
                else:
                    buf.append(text[j])
                    j += 1
            tokens.append("\x00" + "".join(buf))
            i = j
        else:
            j = i
            while j < n and text[j] not in ' \t\n\r()"':
                j += 1
            tokens.append(text[i:j])
            i = j
    return tokens


def _read(tokens: list[str], pos: int) -> tuple[SExpr, int]:
    if pos >= len(tokens):
        raise ValueError("Unexpected end of input")
    tok = tokens[pos]
    if tok == "(":
        pos += 1
        children: list[SExpr] = []
        while pos < len(tokens) and tokens[pos] != ")":
            child, pos = _read(tokens, pos)
            children.append(child)
        if pos >= len(tokens):
            raise ValueError("Unmatched '('")
        return children, pos + 1
    if tok == ")":
        raise ValueError("Unexpected ')'")
    if tok.startswith("\x00"):
        return QuotedStr(tok[1:]), pos + 1
    return tok, pos + 1
