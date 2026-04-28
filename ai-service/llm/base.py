from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolCall:
    """Standard shape across providers."""
    id: str
    name: str
    arguments: dict


@dataclass
class ChatTurn:
    """Provider-agnostic chat result.

    Either `text` is a final answer, or `tool_calls` requests one or more
    tools to be executed and the result fed back into the next turn.
    """
    text: str | None
    tool_calls: list[ToolCall]


class LLMProvider(ABC):
    """Common interface for all LLM backends."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """One-shot completion (kept for backward compat)."""
        raise NotImplementedError

    @abstractmethod
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ChatTurn:
        """Multi-turn chat with optional tool calling.

        messages: [{role, content}] or assistant turn with tool_calls,
                  or {role: 'tool', tool_call_id, content} for tool results.
        tools:    OpenAI-style function schemas (or None to disable).
        """
        raise NotImplementedError
