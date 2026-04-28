from __future__ import annotations

import os

from anthropic import Anthropic

from .base import ChatTurn, LLMProvider, ToolCall


class ClaudeProvider(LLMProvider):
    def __init__(self) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self.client = Anthropic(api_key=api_key)
        self.model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

    def generate(self, prompt: str) -> str:
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
        return "".join(parts).strip()

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ChatTurn:
        # Anthropic's tool format differs slightly; flatten OpenAI-style schemas.
        anth_tools = None
        if tools:
            anth_tools = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"]["description"],
                    "input_schema": t["function"]["parameters"],
                }
                for t in tools
            ]

        # Translate OpenAI-style messages → Anthropic format.
        anth_messages: list[dict] = []
        system_text = None
        for m in messages:
            role = m.get("role")
            if role == "system":
                system_text = m.get("content")
                continue
            if role == "tool":
                anth_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": m["tool_call_id"],
                        "content": m["content"],
                    }],
                })
                continue
            if role == "assistant" and m.get("tool_calls"):
                blocks = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for tc in m["tool_calls"]:
                    blocks.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": tc["function"]["arguments"],
                    })
                anth_messages.append({"role": "assistant", "content": blocks})
                continue
            anth_messages.append({"role": role, "content": m.get("content", "")})

        kwargs: dict = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": anth_messages,
        }
        if system_text:
            kwargs["system"] = system_text
        if anth_tools:
            kwargs["tools"] = anth_tools

        msg = self.client.messages.create(**kwargs)

        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for b in msg.content:
            t = getattr(b, "type", None)
            if t == "text":
                text_parts.append(b.text)
            elif t == "tool_use":
                calls.append(ToolCall(id=b.id, name=b.name, arguments=dict(b.input)))

        return ChatTurn(text=("".join(text_parts).strip() or None), tool_calls=calls)
