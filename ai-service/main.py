"""FastAPI entrypoint — exposes the tool-calling agent over HTTP."""
from __future__ import annotations

import os
import time
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

# Logging must be set up before any module imports it.
from core.logging_setup import get_logger, new_request_id, setup_logging  # noqa: E402

setup_logging()
log = get_logger(__name__)

from agent import Agent, steps_as_dicts  # noqa: E402
from llm import get_llm  # noqa: E402
from tools import stock_tools  # noqa: E402
from tools.base import ToolRegistry  # noqa: E402


app = FastAPI(title="Stock AI Service (tool-calling agent)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = new_request_id()
    started = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("http.error", extra={"path": str(request.url.path)})
        raise
    duration_ms = round((time.monotonic() - started) * 1000, 1)
    log.info(
        "http.request",
        extra={
            "method": request.method,
            "path": str(request.url.path),
            "status": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    response.headers["x-request-id"] = rid
    return response


# ----- one registry per service -----
registry = ToolRegistry()
stock_tools.register_all(registry)


def make_agent() -> Agent:
    return Agent(llm=get_llm(), registry=registry)


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    tools_used: list[dict]
    steps: list[dict]


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "provider": os.getenv("LLM_PROVIDER", "ollama"),
        "tools": registry.names(),
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if not req.question or not req.question.strip():
        raise HTTPException(400, "question is required")
    try:
        result = make_agent().ask(req.question)
    except Exception as e:
        log.exception("agent.crash")
        raise HTTPException(502, f"agent error: {type(e).__name__}: {e}")
    return ChatResponse(
        answer=result.answer,
        tools_used=result.tools_used,
        steps=steps_as_dicts(result.steps),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
