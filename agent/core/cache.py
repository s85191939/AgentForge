"""Simple in-memory TTL cache for agent responses.

Caches responses keyed by (thread_id, normalised_query) with a configurable
TTL. Avoids redundant LLM calls for repeated identical questions within the
same conversation thread.

Thread-safe for the single-process asyncio model used by FastAPI/Uvicorn.
"""

from __future__ import annotations

import hashlib
import logging
import time

logger = logging.getLogger("agentforge.cache")


class ResponseCache:
    """In-memory cache with per-entry TTL and bounded size."""

    def __init__(self, ttl_seconds: int = 300, max_size: int = 128) -> None:
        self._cache: dict[str, tuple[float, dict]] = {}
        self._ttl = ttl_seconds
        self._max_size = max_size

    # ------------------------------------------------------------------
    # Key generation
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(message: str, thread_id: str) -> str:
        """Deterministic cache key from normalised query + thread."""
        normalised = message.strip().lower()
        raw = f"{thread_id}:{normalised}"
        return hashlib.sha256(raw.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, message: str, thread_id: str) -> dict | None:
        """Return cached response dict or None on miss / expiry."""
        key = self._make_key(message, thread_id)
        entry = self._cache.get(key)
        if entry is None:
            return None

        ts, data = entry
        if time.time() - ts > self._ttl:
            del self._cache[key]
            return None

        logger.info("Cache HIT for query (key=%s…)", key[:8])
        return data

    def put(self, message: str, thread_id: str, data: dict) -> None:
        """Store a response in the cache."""
        self._evict_expired()

        # Enforce max size — evict oldest entry
        if len(self._cache) >= self._max_size:
            oldest_key = min(self._cache, key=lambda k: self._cache[k][0])
            del self._cache[oldest_key]

        key = self._make_key(message, thread_id)
        self._cache[key] = (time.time(), data)
        logger.debug("Cached response (key=%s…, size=%d)", key[:8], len(self._cache))

    def clear(self) -> None:
        """Flush all entries."""
        self._cache.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _evict_expired(self) -> None:
        """Remove entries older than TTL."""
        now = time.time()
        expired = [k for k, (ts, _) in self._cache.items() if now - ts > self._ttl]
        for k in expired:
            del self._cache[k]

    @property
    def size(self) -> int:
        """Current number of entries (including possibly expired)."""
        return len(self._cache)
