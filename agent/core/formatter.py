"""Output formatter — adds citations, confidence, and structured metadata.

Transforms raw agent responses into enriched output with:
- Data source citations (which tools provided the data)
- Confidence level estimation
- Structured sections (answer, sources, disclaimer)
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("agentforge.formatter")

# ---------------------------------------------------------------------------
# Tool → human-readable data source mapping
# ---------------------------------------------------------------------------

TOOL_SOURCE_LABELS: dict[str, str] = {
    "get_portfolio_holdings": "Portfolio Holdings (Ghostfolio)",
    "get_portfolio_performance": "Performance Metrics (Ghostfolio)",
    "get_portfolio_details": "Portfolio Details (Ghostfolio)",
    "get_orders": "Transaction History (Ghostfolio)",
    "get_accounts": "Account Data (Ghostfolio)",
    "lookup_symbol": "Market Data Lookup (Ghostfolio/Yahoo Finance)",
    "get_user_settings": "User Settings (Ghostfolio)",
    "preview_import": "Import Preview (Validation)",
    "import_activities": "Activity Import (Ghostfolio)",
    "authenticate": "Authentication (Ghostfolio)",
    "health_check": "Health Check (Ghostfolio)",
    "delete_order": "Order Deletion (Ghostfolio)",
    "get_portfolio_news": "Portfolio News (Finnhub via Ghostfolio)",
    "get_symbol_news": "Symbol News (Finnhub via Ghostfolio)",
    "create_news_alert": "News Alert Creation (Ghostfolio)",
    "list_news_alerts": "News Alerts (Ghostfolio)",
    "delete_news_alert": "News Alert Deletion (Ghostfolio)",
    "update_news_alert": "News Alert Update (Ghostfolio)",
}


# ---------------------------------------------------------------------------
# Confidence estimation
# ---------------------------------------------------------------------------

def estimate_confidence(
    response: str,
    tools_called: list[str],
    tool_results: list[str] | None = None,
) -> str:
    """Estimate confidence level of the response.

    Returns one of: 'high', 'medium', 'low'.

    High confidence:
        - Tools were called and returned data
        - Response contains specific numbers (dollar amounts, percentages)

    Medium confidence:
        - Tools called but response is mostly interpretive
        - Some data present but may be incomplete

    Low confidence:
        - No tools called (pure LLM generation)
        - Tool errors detected
        - Hedging language present
    """
    # No tools called → low confidence (LLM is guessing)
    if not tools_called:
        return "low"

    # Check for tool errors
    if tool_results:
        error_indicators = ["error", "failed", "unable", "could not", "no data"]
        for result in tool_results:
            lower = result.lower()
            if any(ind in lower for ind in error_indicators):
                return "low"

    # Check for hedging language
    hedging = [
        r"\bi'?m not sure\b",
        r"\bi don'?t have (enough )?data\b",
        r"\bthis (may|might|could) not be\b",
        r"\bunable to (determine|calculate)\b",
        r"\bapproximate\b",
        r"\bestimate\b",
    ]
    hedge_count = sum(1 for p in hedging if re.search(p, response, re.IGNORECASE))

    # Check for concrete data markers
    has_dollar = bool(re.search(r"\$[\d,]+\.?\d*", response))
    has_pct = bool(re.search(r"\d+\.?\d*%", response))
    has_specific_data = has_dollar or has_pct

    # Score it
    if has_specific_data and hedge_count == 0 and len(tools_called) >= 1:
        return "high"
    elif has_specific_data or len(tools_called) >= 1:
        return "medium"
    else:
        return "low"


# ---------------------------------------------------------------------------
# Citation builder
# ---------------------------------------------------------------------------

def build_citations(tools_called: list[str]) -> list[str]:
    """Build human-readable citation list from tools that were called.

    Returns a list of source labels like:
        ["Portfolio Holdings (Ghostfolio)", "Performance Metrics (Ghostfolio)"]
    """
    seen: set[str] = set()
    citations: list[str] = []

    for tool_name in tools_called:
        # Skip auth/health — they don't provide user data
        if tool_name in ("authenticate", "health_check"):
            continue

        label = TOOL_SOURCE_LABELS.get(tool_name, tool_name)
        if label not in seen:
            seen.add(label)
            citations.append(label)

    return citations


# ---------------------------------------------------------------------------
# Main formatter
# ---------------------------------------------------------------------------

class FormattedResponse:
    """Enriched agent response with citations, confidence, and metadata."""

    def __init__(
        self,
        content: str,
        citations: list[str],
        confidence: str,
        tools_used: list[str],
    ) -> None:
        self.content = content
        self.citations = citations
        self.confidence = confidence
        self.tools_used = tools_used

    def to_dict(self) -> dict:
        """Serialize for API response."""
        return {
            "content": self.content,
            "citations": self.citations,
            "confidence": self.confidence,
            "tools_used": self.tools_used,
        }


def format_response(
    response: str,
    tools_called: list[str],
    tool_results: list[str] | None = None,
) -> FormattedResponse:
    """Format an agent response with citations and confidence.

    Args:
        response: The raw agent text response.
        tools_called: List of tool names that were invoked.
        tool_results: Optional list of raw tool output strings.

    Returns:
        FormattedResponse with enriched metadata.
    """
    citations = build_citations(tools_called)
    confidence = estimate_confidence(response, tools_called, tool_results)

    logger.debug(
        f"Formatted response — confidence={confidence}, "
        f"citations={len(citations)}, tools={len(tools_called)}"
    )

    return FormattedResponse(
        content=response,
        citations=citations,
        confidence=confidence,
        tools_used=tools_called,
    )
