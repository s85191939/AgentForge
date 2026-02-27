"""Unit tests for the in-memory response cache."""

from __future__ import annotations

import time
from unittest.mock import patch

from agent.core.cache import ResponseCache


class TestResponseCache:
    def test_put_and_get(self):
        cache = ResponseCache(ttl_seconds=60, max_size=10)
        data = {"response": "hello", "thread_id": "t1"}
        cache.put("What are my holdings?", "thread-1", data)
        result = cache.get("What are my holdings?", "thread-1")
        assert result == data

    def test_miss_returns_none(self):
        cache = ResponseCache(ttl_seconds=60, max_size=10)
        result = cache.get("nonexistent query", "thread-1")
        assert result is None

    def test_different_threads_different_keys(self):
        cache = ResponseCache(ttl_seconds=60, max_size=10)
        data1 = {"response": "thread1 answer"}
        data2 = {"response": "thread2 answer"}
        cache.put("same query", "thread-1", data1)
        cache.put("same query", "thread-2", data2)

        assert cache.get("same query", "thread-1") == data1
        assert cache.get("same query", "thread-2") == data2

    def test_case_insensitive_and_whitespace_normalised(self):
        cache = ResponseCache(ttl_seconds=60, max_size=10)
        data = {"response": "answer"}
        cache.put("What are my Holdings?", "t1", data)
        result = cache.get("  what are my holdings?  ", "t1")
        assert result == data

    def test_ttl_expiry(self):
        cache = ResponseCache(ttl_seconds=1, max_size=10)
        data = {"response": "ephemeral"}
        cache.put("query", "t1", data)
        assert cache.get("query", "t1") == data

        # Simulate time passing beyond TTL
        with patch("agent.core.cache.time") as mock_time:
            mock_time.time.return_value = time.time() + 2
            result = cache.get("query", "t1")
            assert result is None

    def test_max_size_evicts_oldest(self):
        cache = ResponseCache(ttl_seconds=300, max_size=3)
        cache.put("q1", "t1", {"r": "1"})
        cache.put("q2", "t1", {"r": "2"})
        cache.put("q3", "t1", {"r": "3"})

        # Cache is full (3/3), adding q4 should evict q1 (oldest)
        cache.put("q4", "t1", {"r": "4"})

        assert cache.get("q1", "t1") is None  # evicted
        assert cache.get("q2", "t1") == {"r": "2"}
        assert cache.get("q4", "t1") == {"r": "4"}

    def test_clear(self):
        cache = ResponseCache(ttl_seconds=300, max_size=10)
        cache.put("q1", "t1", {"r": "1"})
        cache.put("q2", "t1", {"r": "2"})
        assert cache.size == 2

        cache.clear()
        assert cache.size == 0
        assert cache.get("q1", "t1") is None

    def test_size_property(self):
        cache = ResponseCache(ttl_seconds=300, max_size=10)
        assert cache.size == 0
        cache.put("q1", "t1", {"r": "1"})
        assert cache.size == 1
        cache.put("q2", "t1", {"r": "2"})
        assert cache.size == 2

    def test_overwrite_same_key(self):
        cache = ResponseCache(ttl_seconds=300, max_size=10)
        cache.put("query", "t1", {"r": "old"})
        cache.put("query", "t1", {"r": "new"})
        assert cache.get("query", "t1") == {"r": "new"}
        assert cache.size == 1

    def test_make_key_is_deterministic(self):
        key1 = ResponseCache._make_key("hello", "thread-1")
        key2 = ResponseCache._make_key("hello", "thread-1")
        assert key1 == key2
        assert len(key1) == 64  # SHA-256 hex digest
