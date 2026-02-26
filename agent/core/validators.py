"""Input validation and sanitization for tool parameters.

Ensures user-supplied strings are safe before reaching the Ghostfolio API.
Guards against injection, excessively long inputs, and invalid parameters.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_QUERY_LENGTH = 200
MAX_SYMBOL_LENGTH = 30
MAX_JSON_LENGTH = 10_000

VALID_RANGES = frozenset({"1d", "wtd", "1w", "mtd", "1m", "3m", "ytd", "1y", "3y", "5y", "max"})

# Control characters (C0 + C1) — never valid in user input
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


# ---------------------------------------------------------------------------
# Generic sanitiser
# ---------------------------------------------------------------------------

def sanitize_string(
    value: str,
    max_length: int = 200,
    field_name: str = "input",
) -> str:
    """Strip whitespace, remove control characters, and truncate.

    Args:
        value: Raw user input.
        max_length: Maximum allowed length after cleaning.
        field_name: Human-readable name for error messages.

    Returns:
        Cleaned string.

    Raises:
        ValueError: If value is not a string or is empty after cleaning.
    """
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string, got {type(value).__name__}")

    cleaned = value.strip()
    cleaned = _CONTROL_CHARS_RE.sub("", cleaned)

    if not cleaned:
        raise ValueError(f"{field_name} cannot be empty")

    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]

    return cleaned


# ---------------------------------------------------------------------------
# Domain-specific validators
# ---------------------------------------------------------------------------

def validate_range(range_value: str) -> str:
    """Validate portfolio time-range parameter.

    Raises:
        ValueError: If the range is not one of the accepted values.
    """
    cleaned = range_value.strip().lower()
    if cleaned not in VALID_RANGES:
        raise ValueError(
            f"Invalid range '{range_value}'. "
            f"Valid options: {', '.join(sorted(VALID_RANGES))}"
        )
    return cleaned


def validate_symbol_query(query: str) -> str:
    """Validate and sanitize a symbol/ticker lookup query.

    Raises:
        ValueError: If query is empty or invalid.
    """
    return sanitize_string(query, max_length=MAX_SYMBOL_LENGTH, field_name="symbol query")


def validate_json_payload(json_str: str, field_name: str = "JSON payload") -> str:
    """Basic length and type check for JSON string payloads.

    Raises:
        ValueError: If the string is too long or not a string.
    """
    if not isinstance(json_str, str):
        raise ValueError(f"{field_name} must be a string")
    if len(json_str) > MAX_JSON_LENGTH:
        raise ValueError(
            f"{field_name} is too large ({len(json_str)} chars, max {MAX_JSON_LENGTH})"
        )
    return json_str
