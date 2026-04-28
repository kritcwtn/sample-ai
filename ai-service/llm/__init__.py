import os
from .base import LLMProvider
from .ollama import OllamaProvider
from .claude import ClaudeProvider


def get_llm() -> LLMProvider:
    """Factory: return the configured LLM provider."""
    name = os.getenv("LLM_PROVIDER", "ollama").lower()
    if name == "claude":
        return ClaudeProvider()
    if name == "ollama":
        return OllamaProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {name}")
