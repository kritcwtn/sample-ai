"""Base classes for the tool-calling agent.

Tools subclass `BaseTool`, declare a JSON-schema `parameters` block, and
implement `run(**kwargs)`. Callers should always go through `execute(args)`
so arguments are validated/clamped and the result is wrapped in a uniform
envelope:

    {
        "count": <int>,           # number of items
        "items": [ ...rows... ],  # list of dict rows (or scalar wrapped)
    }

For aggregate scalars (e.g. total_qty), tools return a dict and BaseTool
wraps it as {"count": 1, "items": [<dict>]} for shape uniformity.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.validators import ToolValidationError, validate_args


class BaseTool(ABC):
    """One callable capability the LLM may use."""

    name: str
    description: str
    # JSON Schema for parameters; default = no params.
    parameters: dict = {"type": "object", "properties": {}}
    # Whether duplicate calls (same name+args in same agent run) are skipped.
    idempotent: bool = True
    # Hint for caching; not wired by default (see core/cache.py).
    cacheable: bool = False

    @abstractmethod
    def run(self, **kwargs: Any) -> Any:
        """Execute the tool. Return either a list[dict] or a single dict."""
        raise NotImplementedError

    def execute(self, args: dict | None = None) -> dict:
        """Validate args, run the tool, return a uniform envelope."""
        clean = validate_args(args or {}, self.parameters)
        raw = self.run(**clean)
        return _envelope(raw)

    def schema(self) -> dict:
        """OpenAI/Ollama-compatible function schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def short(self) -> str:
        """One-line summary for the system prompt's tool catalogue."""
        first_line = (self.description or "").strip().split("\n", 1)[0]
        return f"- {self.name}: {first_line}"


def _envelope(raw: Any) -> dict:
    """Wrap any tool result in {count, items}."""
    if isinstance(raw, dict) and set(raw.keys()) == {"count", "items"}:
        return raw
    if isinstance(raw, list):
        return {"count": len(raw), "items": raw}
    if isinstance(raw, dict):
        return {"count": 1, "items": [raw]}
    return {"count": 0 if raw is None else 1, "items": [] if raw is None else [{"value": raw}]}


class ToolRegistry:
    """Holds the catalogue of tools an agent may call."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def summary(self) -> str:
        """Multi-line tool catalogue, used inside the system prompt."""
        return "\n".join(t.short() for t in self._tools.values())

    def execute(self, name: str, args: dict | None = None) -> dict:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(name)
        return tool.execute(args or {})


# Re-export so callers can `from tools.base import ToolValidationError`.
__all__ = ["BaseTool", "ToolRegistry", "ToolValidationError"]
