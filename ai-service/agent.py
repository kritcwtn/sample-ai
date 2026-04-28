"""Tool-calling agent loop (production-grade).

Responsibilities:
  - Build a domain-aware system prompt with an auto-generated tool catalogue.
  - Run a bounded ReAct loop: LLM → tool → result → LLM → final.
  - Validate / clamp tool arguments before execution (via BaseTool.execute).
  - Capture a structured step trace for observability.
  - Skip duplicate tool calls (same name + same args inside one run).
  - Recover gracefully when a tool fails or the LLM names an unknown tool.
  - Strip stray CJK characters that some Ollama-served models leak.

Returned `AgentResult.steps` is the audit trail consumed by callers
(/chat endpoint, structured log, debugging). One entry per LLM iteration
plus one per tool invocation, in chronological order.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from core.logging_setup import get_logger, safe_extra
from llm.base import LLMProvider
from tools.base import ToolRegistry, ToolValidationError

log = get_logger(__name__)


# Strip CJK ideographs / kana / hangul. qwen2.5 sometimes leaks Chinese.
_CJK_RE = re.compile(
    r"[　-〿぀-ゟ゠-ヿ㐀-䶿一-鿿가-힯＀-￯]+[，。！？：；、]*"
)
_THAI_RE = re.compile(r"[฀-๿]")


def _strip_cjk(text: str) -> str:
    if not text:
        return ""
    had_cjk = bool(_CJK_RE.search(text))
    cleaned = _CJK_RE.sub("", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if had_cjk and "\n\n" in cleaned:
        blocks = [b.strip() for b in cleaned.split("\n\n") if b.strip()]
        thai_blocks = [b for b in blocks if _THAI_RE.search(b)]
        if thai_blocks:
            return thai_blocks[-1]
    return cleaned


# ---- domain prompt ------------------------------------------------------

_SYSTEM_RULES = """\
You are a stock-management assistant.

RULES (must follow):
- For ANY question about products, stock, sales, or inventory: you MUST call \
a tool to read live data. Never answer from memory or invent values.
- Never invent product names, qty values, or sold counts that are not present \
in a tool result.
- For comparisons between specific named products, call \
search_products_by_name once per product (not get_best_sellers).
- Mention only the products the user asked about — do not introduce other \
products from a tool result.
- If a tool returns an empty result, say so politely in Thai and (if relevant) \
suggest the user check spelling.
- If a tool returns an error, apologise briefly and stop — do not retry.
- For questions unrelated to stock/products (weather, recipes, math, coding): \
politely refuse in Thai WITHOUT calling any tool.
- Respond ONLY in Thai. Do NOT include Chinese, Japanese, or Korean characters.
- Be concise: 1-3 sentences.
"""


def build_system_prompt(registry: ToolRegistry) -> str:
    return f"{_SYSTEM_RULES}\nAVAILABLE TOOLS:\n{registry.summary()}\n"


# ---- step trace ---------------------------------------------------------

@dataclass
class StepLog:
    step: int
    tool: str | None = None
    args: dict | None = None
    result_count: int | None = None
    duration_ms: float = 0.0
    error: str | None = None
    skipped: str | None = None  # reason if call was deduped/blocked


@dataclass
class AgentResult:
    answer: str
    tools_used: list[dict] = field(default_factory=list)
    steps: list[StepLog] = field(default_factory=list)


# ---- agent --------------------------------------------------------------

class Agent:
    def __init__(
        self,
        llm: LLMProvider,
        registry: ToolRegistry,
        *,
        max_iters: int = 6,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.max_iters = max_iters

    def ask(self, question: str) -> AgentResult:
        system_prompt = build_system_prompt(self.registry)
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]
        steps: list[StepLog] = []
        tools_used: list[dict] = []
        seen: set[tuple[str, str]] = set()  # (tool_name, args_json) → dedup
        unknown_retry_done = False

        log.info("agent.start", extra=safe_extra(question=question))

        for i in range(1, self.max_iters + 1):
            turn_started = time.monotonic()
            turn = self.llm.chat(messages, tools=self.registry.schemas())
            llm_ms = round((time.monotonic() - turn_started) * 1000, 1)

            if not turn.tool_calls:
                # final answer
                answer = _strip_cjk((turn.text or "").strip())
                steps.append(StepLog(step=i, duration_ms=llm_ms))
                log.info(
                    "agent.final",
                    extra=safe_extra(step=i, answer_len=len(answer), duration_ms=llm_ms),
                )
                return AgentResult(answer=answer, tools_used=tools_used, steps=steps)

            # Append assistant turn for the next iteration.
            messages.append({
                "role": "assistant",
                "content": turn.text or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments},
                    }
                    for tc in turn.tool_calls
                ],
            })

            for tc in turn.tool_calls:
                step_started = time.monotonic()
                step = StepLog(step=i, tool=tc.name, args=tc.arguments)
                key = (tc.name, json.dumps(tc.arguments, sort_keys=True, default=str))

                tool = self.registry.get(tc.name)
                if tool is None:
                    # Recover from a hallucinated tool name — retry once with hint.
                    available = ", ".join(self.registry.names())
                    hint = f"Tool '{tc.name}' does not exist. Available tools: {available}. Try again."
                    step.error = "unknown_tool"
                    step.duration_ms = round((time.monotonic() - step_started) * 1000, 1)
                    steps.append(step)
                    log.warning(
                        "agent.unknown_tool",
                        extra=safe_extra(step=i, tool=tc.name, available=self.registry.names()),
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": json.dumps({"error": hint}, ensure_ascii=False),
                    })
                    if unknown_retry_done:
                        # Already retried once — bail to avoid infinite loops.
                        break
                    unknown_retry_done = True
                    continue

                if tool.idempotent and key in seen:
                    step.skipped = "duplicate_call"
                    step.duration_ms = round((time.monotonic() - step_started) * 1000, 1)
                    steps.append(step)
                    log.info("agent.dedup", extra=safe_extra(step=i, tool=tc.name))
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": json.dumps(
                            {"info": "duplicate call skipped — refer to previous result"},
                            ensure_ascii=False,
                        ),
                    })
                    continue
                seen.add(key)

                try:
                    envelope = tool.execute(tc.arguments)
                    step.result_count = envelope.get("count", 0)
                    tool_payload: dict = envelope
                except ToolValidationError as e:
                    step.error = f"validation: {e}"
                    tool_payload = {"error": str(e), "count": 0, "items": []}
                except Exception as e:  # last-resort safety net
                    step.error = f"runtime: {type(e).__name__}: {e}"
                    tool_payload = {"error": "tool failed", "count": 0, "items": []}
                step.duration_ms = round((time.monotonic() - step_started) * 1000, 1)
                steps.append(step)

                log.info(
                    "agent.tool",
                    extra=safe_extra(
                        step=i,
                        tool=tc.name,
                        args=tc.arguments,
                        result_count=step.result_count,
                        duration_ms=step.duration_ms,
                        error=step.error,
                    ),
                )

                tools_used.append(
                    {"name": tc.name, "arguments": tc.arguments, "result": tool_payload}
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": json.dumps(tool_payload, ensure_ascii=False),
                })

        # Iteration cap reached — ask LLM to wrap up with what it has.
        log.warning("agent.iters_exhausted", extra=safe_extra(max_iters=self.max_iters))
        messages.append({
            "role": "user",
            "content": "Based on the tool results above, give the final answer in Thai now.",
        })
        final = self.llm.chat(messages, tools=None)
        answer = _strip_cjk((final.text or "").strip())
        return AgentResult(answer=answer, tools_used=tools_used, steps=steps)


# Convenience: serialise step list for JSON responses.
def steps_as_dicts(steps: list[StepLog]) -> list[dict]:
    return [asdict(s) for s in steps]
