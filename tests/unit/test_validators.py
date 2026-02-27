"""Unit tests for input validation and sanitization."""

from __future__ import annotations

import pytest

from agent.core.validators import (
    MAX_JSON_LENGTH,
    MAX_SYMBOL_LENGTH,
    VALID_RANGES,
    sanitize_string,
    validate_json_payload,
    validate_range,
    validate_symbol_query,
)

# ---------------------------------------------------------------------------
# sanitize_string
# ---------------------------------------------------------------------------


class TestSanitizeString:
    def test_strips_whitespace(self):
        assert sanitize_string("  hello  ") == "hello"

    def test_removes_control_characters(self):
        assert sanitize_string("hello\x00world\x1f") == "helloworld"

    def test_truncates_long_input(self):
        result = sanitize_string("a" * 300, max_length=200)
        assert len(result) == 200

    def test_raises_on_non_string(self):
        with pytest.raises(ValueError, match="must be a string"):
            sanitize_string(123)  # type: ignore

    def test_raises_on_empty_after_cleaning(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            sanitize_string("   ")

    def test_raises_on_only_control_chars(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            sanitize_string("\x00\x01\x02")

    def test_custom_field_name_in_error(self):
        with pytest.raises(ValueError, match="order ID cannot be empty"):
            sanitize_string("", field_name="order ID")

    def test_preserves_unicode(self):
        assert sanitize_string("caf\u00e9") == "caf\u00e9"

    def test_custom_max_length(self):
        result = sanitize_string("abcdefghij", max_length=5)
        assert result == "abcde"


# ---------------------------------------------------------------------------
# validate_range
# ---------------------------------------------------------------------------


class TestValidateRange:
    def test_all_valid_ranges(self):
        for r in VALID_RANGES:
            assert validate_range(r) == r

    def test_case_insensitive(self):
        assert validate_range("YTD") == "ytd"
        assert validate_range("Max") == "max"

    def test_strips_whitespace(self):
        assert validate_range("  1d  ") == "1d"

    def test_invalid_range_raises(self):
        with pytest.raises(ValueError, match="Invalid range"):
            validate_range("2y")

    def test_empty_range_raises(self):
        with pytest.raises(ValueError, match="Invalid range"):
            validate_range("")


# ---------------------------------------------------------------------------
# validate_symbol_query
# ---------------------------------------------------------------------------


class TestValidateSymbolQuery:
    def test_valid_symbol(self):
        assert validate_symbol_query("AAPL") == "AAPL"

    def test_strips_and_cleans(self):
        assert validate_symbol_query("  MSFT  ") == "MSFT"

    def test_truncates_to_max_length(self):
        long_query = "A" * 50
        result = validate_symbol_query(long_query)
        assert len(result) == MAX_SYMBOL_LENGTH

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            validate_symbol_query("   ")


# ---------------------------------------------------------------------------
# validate_json_payload
# ---------------------------------------------------------------------------


class TestValidateJsonPayload:
    def test_valid_json_string(self):
        payload = '{"symbol": "AAPL", "type": "BUY"}'
        assert validate_json_payload(payload) == payload

    def test_raises_on_non_string(self):
        with pytest.raises(ValueError, match="must be a string"):
            validate_json_payload(123)  # type: ignore

    def test_raises_on_too_large(self):
        big_payload = "x" * (MAX_JSON_LENGTH + 1)
        with pytest.raises(ValueError, match="too large"):
            validate_json_payload(big_payload)

    def test_custom_field_name(self):
        with pytest.raises(ValueError, match="activities must be a string"):
            validate_json_payload(42, field_name="activities")  # type: ignore
