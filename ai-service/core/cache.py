"""Tiny TTL cache — interface stub for now.

Stock data mutates frequently (sell button, edits) so we leave caching OFF
by default in the agent. This module exists so future tools whose results
are immutable (e.g. lookup tables, schema introspection) can opt in by
calling `cache.get_or_compute(...)` directly.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable


class TTLCache:
    def __init__(self, ttl_seconds: int = 60, maxsize: int = 256) -> None:
        self.ttl = ttl_seconds
        self.maxsize = maxsize
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            expires_at, value = item
            if time.time() > expires_at:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._store) >= self.maxsize:
                # naive eviction — drop oldest
                oldest = min(self._store, key=lambda k: self._store[k][0])
                self._store.pop(oldest, None)
            self._store[key] = (time.time() + self.ttl, value)

    def get_or_compute(self, key: str, fn: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = fn()
        self.set(key, value)
        return value


# A single module-level instance is cheap and avoids passing it around.
default_cache = TTLCache(ttl_seconds=60)
