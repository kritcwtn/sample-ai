"""Lightweight argument validation driven by the tool's JSON Schema.

Designed to keep BaseTool definitions free of any framework dependency
(no Pydantic). Reads `parameters` JSON Schema and:
  - coerces types (str → int / float / bool when sensible)
  - drops unknown keys
  - applies defaults
  - clamps numerics to declared minimum/maximum
  - enforces required keys
"""
from __future__ import annotations

from typing import Any


class ToolValidationError(ValueError):
    """Raised when arguments don't conform to a tool's parameter schema."""


def clamp_int(value: Any, lo: int, hi: int, default: int | None = None) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        if default is not None:
            return default
        raise ToolValidationError(f"expected integer, got {value!r}")
    return max(lo, min(hi, n))


def clamp_float(value: Any, lo: float, hi: float, default: float | None = None) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        if default is not None:
            return default
        raise ToolValidationError(f"expected number, got {value!r}")
    return max(lo, min(hi, n))


def _coerce(value: Any, schema: dict) -> Any:
    t = schema.get("type")
    if value is None:
        return value
    if t == "integer":
        return clamp_int(
            value,
            int(schema.get("minimum", -10**9)),
            int(schema.get("maximum", 10**9)),
        )
    if t == "number":
        return clamp_float(
            value,
            float(schema.get("minimum", -1e18)),
            float(schema.get("maximum", 1e18)),
        )
    if t == "string":
        s = str(value)
        max_len = int(schema.get("maxLength", 500))
        return s[:max_len]
    if t == "boolean":
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y"}
        return bool(value)
    return value  # unknown type — pass through


def validate_args(args: dict | None, parameters: dict) -> dict:
    """Return a clean, validated args dict per the JSON-schema-style spec."""
    args = args or {}
    properties = parameters.get("properties", {}) or {}
    required = set(parameters.get("required", []) or [])
    out: dict = {}

    for key, spec in properties.items():
        if key in args:
            out[key] = _coerce(args[key], spec)
        elif "default" in spec:
            out[key] = spec["default"]
        elif key in required:
            raise ToolValidationError(f"missing required argument: {key}")
    return out
