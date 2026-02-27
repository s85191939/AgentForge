"""Unit tests for the output formatter module."""

from __future__ import annotations

from agent.core.formatter import (
    TOOL_SOURCE_LABELS,
    FormattedResponse,
    build_citations,
    estimate_confidence,
    format_response,
)

# ---------------------------------------------------------------------------
# TOOL_SOURCE_LABELS completeness
# ---------------------------------------------------------------------------


class TestToolSourceLabels:
    """Verify all 18 tools have human-readable labels."""

    EXPECTED_TOOLS = [
        "get_portfolio_holdings",
        "get_portfolio_performance",
        "get_portfolio_details",
        "get_orders",
        "get_accounts",
        "lookup_symbol",
        "get_user_settings",
        "preview_import",
        "import_activities",
        "authenticate",
        "health_check",
        "delete_order",
        "get_portfolio_news",
        "get_symbol_news",
        "create_news_alert",
        "list_news_alerts",
        "delete_news_alert",
        "update_news_alert",
    ]

    def test_all_tools_have_labels(self):
        for tool_name in self.EXPECTED_TOOLS:
            assert tool_name in TOOL_SOURCE_LABELS, (
                f"Tool '{tool_name}' missing from TOOL_SOURCE_LABELS"
            )

    def test_labels_are_non_empty_strings(self):
        for tool_name, label in TOOL_SOURCE_LABELS.items():
            assert isinstance(label, str) and len(label) > 0, (
                f"Label for '{tool_name}' is invalid"
            )


# ---------------------------------------------------------------------------
# Confidence estimation
# ---------------------------------------------------------------------------


class TestEstimateConfidence:
    def test_no_tools_returns_low(self):
        assert estimate_confidence("response text", []) == "low"

    def test_tool_error_returns_low(self):
        result = estimate_confidence(
            "Here's your data",
            ["get_portfolio_holdings"],
            ["Error: unable to fetch data"],
        )
        assert result == "low"

    def test_hedging_language_reduces_confidence(self):
        result = estimate_confidence(
            "I'm not sure about the exact numbers, approximately $50,000",
            ["get_portfolio_holdings"],
        )
        # Has hedging ("I'm not sure", "approximately") but also has dollar amount
        assert result in ("medium", "low")

    def test_high_confidence_with_data_and_tools(self):
        result = estimate_confidence(
            "Your portfolio is worth $50,000 with a 10.5% return.",
            ["get_portfolio_holdings", "get_portfolio_performance"],
        )
        assert result == "high"

    def test_medium_confidence_with_tools_no_data(self):
        result = estimate_confidence(
            "You have several holdings in your portfolio.",
            ["get_portfolio_holdings"],
        )
        assert result == "medium"


# ---------------------------------------------------------------------------
# Citation builder
# ---------------------------------------------------------------------------


class TestBuildCitations:
    def test_skips_auth_and_health(self):
        citations = build_citations(["authenticate", "health_check"])
        assert citations == []

    def test_maps_tool_to_label(self):
        citations = build_citations(["get_portfolio_holdings"])
        assert citations == ["Portfolio Holdings (Ghostfolio)"]

    def test_deduplicates(self):
        citations = build_citations([
            "get_portfolio_holdings",
            "get_portfolio_holdings",
        ])
        assert len(citations) == 1

    def test_unknown_tool_uses_raw_name(self):
        citations = build_citations(["some_unknown_tool"])
        assert citations == ["some_unknown_tool"]

    def test_multiple_tools(self):
        citations = build_citations([
            "get_portfolio_holdings",
            "get_portfolio_performance",
            "get_orders",
        ])
        assert len(citations) == 3
        assert "Portfolio Holdings (Ghostfolio)" in citations
        assert "Performance Metrics (Ghostfolio)" in citations
        assert "Transaction History (Ghostfolio)" in citations

    def test_news_tools_have_labels(self):
        citations = build_citations(["get_portfolio_news", "get_symbol_news"])
        assert "Portfolio News (Finnhub via Ghostfolio)" in citations
        assert "Symbol News (Finnhub via Ghostfolio)" in citations


# ---------------------------------------------------------------------------
# FormattedResponse
# ---------------------------------------------------------------------------


class TestFormattedResponse:
    def test_to_dict(self):
        fr = FormattedResponse(
            content="test",
            citations=["Source A"],
            confidence="high",
            tools_used=["tool1"],
        )
        d = fr.to_dict()
        assert d["content"] == "test"
        assert d["citations"] == ["Source A"]
        assert d["confidence"] == "high"
        assert d["tools_used"] == ["tool1"]


# ---------------------------------------------------------------------------
# format_response integration
# ---------------------------------------------------------------------------


class TestFormatResponse:
    def test_returns_formatted_response(self):
        result = format_response(
            "Your portfolio is worth $50,000.",
            ["get_portfolio_holdings"],
        )
        assert isinstance(result, FormattedResponse)
        assert result.content == "Your portfolio is worth $50,000."
        assert len(result.citations) == 1
        assert result.confidence == "high"

    def test_empty_tools(self):
        result = format_response("No tools were called.", [])
        assert result.citations == []
        assert result.confidence == "low"
