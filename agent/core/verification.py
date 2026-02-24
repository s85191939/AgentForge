"""Domain-specific verification checks for financial agent responses.

Three categories of checks:
1. Numeric consistency  — allocation sums, buy/sell math, value sanity
2. Prohibited advice    — block investment recommendations / financial advice
3. Tool-data completeness — ensure tools returned real data before answering
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("agentforge.verification")

# ---------------------------------------------------------------------------
# 1. Prohibited financial advice language
# ---------------------------------------------------------------------------

# Phrases that constitute financial advice (case-insensitive)
PROHIBITED_PHRASES = [
    r"\bi recommend (buying|selling|investing|holding)\b",
    r"\byou should (buy|sell|invest in|hold|dump|short)\b",
    r"\bmy advice is\b",
    r"\bi advise you to\b",
    r"\byou must (buy|sell|invest)\b",
    r"\bguaranteed returns?\b",
    r"\brisk[- ]free (investment|return)\b",
    r"\bcan'?t lose\b",
    r"\bsure thing\b",
    r"\bfinancial advice\b(?!.*not\b)(?!.*disclaimer\b)",
]

_PROHIBITED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in PROHIBITED_PHRASES]

DISCLAIMER = (
    "\n\n*Disclaimer: This is informational only and not investment advice. "
    "Consult a licensed financial advisor before making investment decisions.*"
)


def check_prohibited_advice(response: str) -> tuple[str, list[str]]:
    """Check response for prohibited financial advice language.

    Returns:
        (cleaned_response, list_of_violations)
        If violations found, the response is cleaned by appending a disclaimer.
    """
    violations: list[str] = []

    for pattern in _PROHIBITED_PATTERNS:
        matches = pattern.findall(response)
        if matches:
            violations.append(f"Prohibited phrase detected: {pattern.pattern}")

    if violations:
        logger.warning(f"Advice violations found: {violations}")
        # Don't block the response — append disclaimer if not already present
        if "not investment advice" not in response.lower():
            response = response + DISCLAIMER

    return response, violations


# ---------------------------------------------------------------------------
# 2. Numeric consistency checks
# ---------------------------------------------------------------------------

def check_allocation_sum(response: str) -> tuple[bool, str | None]:
    """Check if allocation percentages mentioned in response sum to ~100%.

    Extracts all percentage values that look like allocations and verifies
    they sum to approximately 100% (within 5% tolerance).

    Returns:
        (is_valid, warning_message_or_none)
    """
    # Look for patterns like "30.5%" or "allocation: 25%"
    pct_pattern = re.compile(r"(\d+\.?\d*)\s*%")
    matches = pct_pattern.findall(response)

    if len(matches) < 3:
        # Not enough percentages to be an allocation breakdown
        return True, None

    values = [float(m) for m in matches]

    # Filter to likely allocation values (0-100 range, not performance returns)
    alloc_values = [v for v in values if 0 < v <= 100]

    if len(alloc_values) < 3:
        return True, None

    total = sum(alloc_values)

    # Check if it looks like an allocation (sum near 100%)
    if 95 <= total <= 105:
        return True, None
    elif 50 <= total <= 200:
        # Could be an allocation that's off — warn
        warning = (
            f"[Verification] Allocation percentages sum to {total:.1f}% "
            f"(expected ~100%). Values: {alloc_values}"
        )
        logger.warning(warning)
        return False, warning

    # Doesn't look like allocation data, skip
    return True, None


def check_negative_values(response: str) -> tuple[bool, str | None]:
    """Flag potentially incorrect negative portfolio values.

    Holdings values and quantities should generally not be negative.

    Returns:
        (is_valid, warning_message_or_none)
    """
    # Check for negative holdings values like "Value: -$5000" or "-5000 shares"
    neg_value = re.compile(r"(?:value|worth|balance).*?-\$[\d,]+", re.IGNORECASE)
    neg_shares = re.compile(r"-\d+\.?\d*\s*shares?", re.IGNORECASE)

    issues: list[str] = []

    if neg_value.search(response):
        issues.append("Negative portfolio value detected")
    if neg_shares.search(response):
        issues.append("Negative share quantity detected")

    if issues:
        warning = f"[Verification] Suspicious values: {', '.join(issues)}"
        logger.warning(warning)
        return False, warning

    return True, None


# ---------------------------------------------------------------------------
# 3. Tool-data completeness checks
# ---------------------------------------------------------------------------

# Phrases that indicate the tool returned no data
EMPTY_DATA_INDICATORS = [
    "no holdings found",
    "no transactions found",
    "no data available",
    "n/a",
    "empty portfolio",
    "no accounts found",
    "could not retrieve",
    "error fetching",
    "unable to fetch",
]


def check_tool_data_completeness(
    response: str,
    tool_results: list[str] | None = None,
) -> tuple[bool, str | None]:
    """Verify tools returned actual data before the agent answered.

    Checks if tool results contain empty/error indicators, and flags
    responses that present data without a tool having returned it.

    Returns:
        (is_valid, warning_message_or_none)
    """
    if not tool_results:
        return True, None

    empty_tools: list[int] = []

    for i, result in enumerate(tool_results):
        lower = result.lower()
        for indicator in EMPTY_DATA_INDICATORS:
            if indicator in lower:
                empty_tools.append(i)
                break

    if empty_tools and _response_claims_data(response):
        warning = (
            f"[Verification] Agent presented data but tool(s) "
            f"returned empty/error results (tools: {empty_tools})"
        )
        logger.warning(warning)
        return False, warning

    return True, None


def _response_claims_data(response: str) -> bool:
    """Check if the response appears to present specific financial data."""
    # Look for concrete data patterns (dollar amounts, percentages, lists)
    has_dollar = bool(re.search(r"\$[\d,]+\.?\d*", response))
    has_pct = bool(re.search(r"\d+\.?\d*%", response))
    has_list = response.count("\n- ") >= 2

    return has_dollar or (has_pct and has_list)


# ---------------------------------------------------------------------------
# Main verification runner
# ---------------------------------------------------------------------------

class VerificationResult:
    """Result of running all verification checks."""

    def __init__(self) -> None:
        self.passed = True
        self.warnings: list[str] = []
        self.advice_violations: list[str] = []
        self.cleaned_response: str = ""

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def summary(self) -> str:
        if self.passed and not self.has_warnings:
            return "All verification checks passed."
        parts = []
        if self.advice_violations:
            parts.append(f"Advice violations: {len(self.advice_violations)}")
        if self.warnings:
            parts.append(f"Warnings: {len(self.warnings)}")
        return "; ".join(parts)


def verify_response(
    response: str,
    tool_results: list[str] | None = None,
) -> VerificationResult:
    """Run all domain-specific verification checks on an agent response.

    Args:
        response: The agent's final text response.
        tool_results: List of raw tool output strings (if available).

    Returns:
        VerificationResult with cleaned response and any warnings.
    """
    result = VerificationResult()

    # 1. Check for prohibited financial advice
    cleaned, advice_violations = check_prohibited_advice(response)
    result.cleaned_response = cleaned
    result.advice_violations = advice_violations
    if advice_violations:
        result.passed = False

    # 2. Numeric consistency — allocation sum
    alloc_ok, alloc_warn = check_allocation_sum(response)
    if not alloc_ok and alloc_warn:
        result.warnings.append(alloc_warn)

    # 3. Numeric consistency — negative values
    neg_ok, neg_warn = check_negative_values(response)
    if not neg_ok and neg_warn:
        result.warnings.append(neg_warn)

    # 4. Tool-data completeness
    data_ok, data_warn = check_tool_data_completeness(response, tool_results)
    if not data_ok and data_warn:
        result.warnings.append(data_warn)
        result.passed = False

    if result.passed and not result.has_warnings:
        logger.debug("All verification checks passed.")
    else:
        logger.info(f"Verification: {result.summary()}")

    return result
