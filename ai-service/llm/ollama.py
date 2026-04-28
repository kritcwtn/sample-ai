from __future__ import annotations

import json
import os
import re
import uuid

import httpx

from .base import ChatTurn, LLMProvider, ToolCall


# Some Qwen builds occasionally emit tool calls as text using their
# native format <tool_call>{...}</tool_call> instead of populating Ollama's
# structured `tool_calls` field. We also see partial variants where the
# opening tag is missing or mangled (e.g. "itempty\n{...}\n</tool_call>").
# These regexes try the strict form first, then a loose form that just
# looks for a `{"name": ..., "arguments": ...}` JSON object near a closing tag.
_TC_STRICT_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
# Loose: any JSON-looking object that contains both "name" and "arguments" keys.
# Allow either quoted ("name": "x") or unquoted ("name": x) identifier values.
_TC_LOOSE_RE = re.compile(
    r'(\{\s*"name"\s*:\s*"?[\w_]+"?\s*,\s*"arguments"\s*:\s*\{[^{}]*\}\s*\})',
    re.DOTALL,
)


class OllamaProvider(LLMProvider):
    def __init__(self) -> None:
        self.url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

    # ----- legacy single-shot path -----
    def generate(self, prompt: str) -> str:
        resp = httpx.post(
            f"{self.url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0, "top_p": 0.9, "num_ctx": 4096},
            },
            timeout=300.0,
        )
        resp.raise_for_status()
        return (resp.json().get("response") or "").strip()

    # ----- tool-calling path -----
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ChatTurn:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0, "num_ctx": 8192},
        }
        if tools:
            payload["tools"] = tools

        resp = httpx.post(f"{self.url}/api/chat", json=payload, timeout=300.0)
        resp.raise_for_status()
        msg = resp.json().get("message") or {}
        content = msg.get("content") or ""

        calls: list[ToolCall] = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            calls.append(
                ToolCall(
                    id=tc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                    name=fn.get("name", ""),
                    arguments=fn.get("arguments") or {},
                )
            )

        # Fallback: parse qwen-native <tool_call> blocks embedded in content.
        if not calls:
            extracted, leftover = _extract_text_tool_calls(content)
            if extracted:
                calls = extracted
                content = leftover

        return ChatTurn(text=(content.strip() or None), tool_calls=calls)


def _extract_text_tool_calls(content: str) -> tuple[list[ToolCall], str]:
    """Pull tool-call JSON out of free text using strict-then-loose matching."""
    calls: list[ToolCall] = []
    leftover = content

    # 1) strict <tool_call>...</tool_call>
    for match in _TC_STRICT_RE.finditer(content):
        tc = _parse_tool_obj(match.group(1))
        if tc:
            calls.append(tc)
    if calls:
        return calls, _TC_STRICT_RE.sub("", content).strip()

    # 2) loose: any embedded `{"name": ..., "arguments": {...}}` block
    for match in _TC_LOOSE_RE.finditer(content):
        tc = _parse_tool_obj(match.group(1))
        if tc:
            calls.append(tc)
    if calls:
        leftover = _TC_LOOSE_RE.sub("", content)
        leftover = re.sub(r"</?tool_call>", "", leftover).strip()
    return calls, leftover


def _parse_tool_obj(raw: str) -> ToolCall | None:
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        obj = _try_loose_json(raw)
    if not isinstance(obj, dict) or "name" not in obj:
        return None
    return ToolCall(
        id=f"call_{uuid.uuid4().hex[:8]}",
        name=str(obj["name"]),
        arguments=obj.get("arguments") or {},
    )


def _try_loose_json(raw: str) -> dict | None:
    """Best-effort recovery for slightly malformed JSON like
    {"name": list_products, "arguments": {}}  (unquoted identifier)."""
    fixed = re.sub(r'("name"\s*:\s*)([A-Za-z_][\w\.]*)', r'\1"\2"', raw)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        return None
