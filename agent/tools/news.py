"""Financial news and sentiment tools — Finnhub-backed, cached in Ghostfolio."""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from agent.core.validators import sanitize_string, validate_symbol_query
from agent.tools.auth import get_client

logger = logging.getLogger("agentforge.tools.news")


@tool
async def get_portfolio_news() -> str:
    """Get recent financial news for all holdings in the portfolio.

    Returns the latest news articles for each stock in the portfolio,
    including headline, source, sentiment (positive/negative/neutral),
    and publication date.

    News is sourced from Finnhub and cached for 1 hour.

    Use this when the user asks about:
    - News affecting their portfolio
    - What's happening with their stocks
    - Recent headlines for their holdings
    - Market sentiment for their positions
    """
    client = get_client()
    try:
        data = await client.get_portfolio_news()
    except Exception as e:
        logger.error("Failed to fetch portfolio news: %s", e)
        return "Unable to fetch portfolio news. The news service may be unavailable."

    articles = data.get("articles", [])
    symbols = data.get("symbols", [])

    if not articles:
        return (
            f"No recent news found for your portfolio holdings "
            f"({', '.join(symbols[:5])}). News may not be available "
            f"for all assets."
        )

    lines: list[str] = []
    for a in articles[:15]:
        sentiment = a.get("sentiment", "neutral")
        icon = {"positive": "+", "negative": "-", "neutral": "~"}.get(
            sentiment, "~"
        )
        headline = a.get("headline", "No headline")
        symbol = a.get("symbol", "???")
        source = a.get("source", "Unknown")
        pub = a.get("published_at", "")[:10]
        lines.append(f"  [{icon}] {symbol} — {headline} ({source}, {pub})")

    return (
        f"Portfolio News ({len(articles)} articles for "
        f"{', '.join(symbols[:5])}"
        f"{'...' if len(symbols) > 5 else ''}):\n"
        + "\n".join(lines)
    )


@tool
async def get_symbol_news(symbol: str) -> str:
    """Get recent financial news for a specific stock or asset.

    Args:
        symbol: Ticker symbol (e.g., "AAPL", "MSFT", "TSLA").

    Returns recent news articles with headline, source, sentiment,
    and publication date. News is sourced from Finnhub and cached
    for 1 hour.

    Use this when the user asks about news for a specific company
    or ticker symbol.
    """
    try:
        symbol = validate_symbol_query(symbol)
    except ValueError as e:
        return f"Invalid symbol: {e}"

    client = get_client()
    try:
        data = await client.get_news(symbol)
    except Exception as e:
        logger.error("Failed to fetch news for %s: %s", symbol, e)
        return f"Unable to fetch news for {symbol}."

    articles = data.get("articles", [])

    if not articles:
        return f"No recent news found for {symbol}."

    lines: list[str] = []
    for a in articles[:10]:
        sentiment = a.get("sentiment", "neutral")
        icon = {"positive": "+", "negative": "-", "neutral": "~"}.get(
            sentiment, "~"
        )
        headline = a.get("headline", "No headline")
        source = a.get("source", "Unknown")
        pub = a.get("published_at", "")[:10]
        lines.append(f"  [{icon}] {headline} ({source}, {pub})")

    return (
        f"News for {symbol} ({len(articles)} articles):\n"
        + "\n".join(lines)
    )


@tool
async def create_news_alert(symbol: str, keywords: str = "") -> str:
    """Create a news alert for a stock symbol.

    Args:
        symbol: Ticker symbol to monitor (e.g., "AAPL").
        keywords: Optional comma-separated keywords to filter
            (e.g., "earnings,dividend,CEO").

    The alert is stored in Ghostfolio's database and can be listed
    or deleted later. Use this when the user wants to track news
    for a specific stock.
    """
    try:
        symbol = validate_symbol_query(symbol)
    except ValueError as e:
        return f"Invalid symbol: {e}"

    client = get_client()
    try:
        result = await client.create_news_alert(
            symbol, keywords if keywords else None
        )
        alert_id = result.get("id", "unknown")
        return (
            f"News alert created for {symbol}"
            f"{f' (keywords: {keywords})' if keywords else ''}. "
            f"Alert ID: {alert_id}"
        )
    except Exception as e:
        logger.error("Failed to create alert for %s: %s", symbol, e)
        return f"Failed to create news alert: {e}"


@tool
async def list_news_alerts() -> str:
    """List all active news alerts.

    Returns all news alerts the user has created, including the
    monitored symbol, keywords, and whether the alert is active.

    Use this when the user asks about their alerts, watched stocks,
    or monitored symbols.
    """
    client = get_client()
    try:
        alerts = await client.list_news_alerts()
    except Exception as e:
        logger.error("Failed to list alerts: %s", e)
        return "Unable to fetch news alerts."

    if not alerts:
        return "No news alerts configured. Use create_news_alert to add one."

    lines: list[str] = []
    for a in alerts:
        status = "Active" if a.get("is_active", True) else "Paused"
        kw = a.get("keywords", "")
        kw_str = f" (keywords: {kw})" if kw else ""
        lines.append(
            f"  - {a.get('symbol', '???')}{kw_str} [{status}] "
            f"(ID: {a.get('id', 'N/A')})"
        )

    return f"News Alerts ({len(alerts)}):\n" + "\n".join(lines)


@tool
async def delete_news_alert(alert_id: str) -> str:
    """Delete a news alert by its ID.

    Args:
        alert_id: The UUID of the alert to delete.
            Get alert IDs from the list_news_alerts tool.

    Use this when the user wants to stop monitoring news for a symbol.
    """
    try:
        alert_id = sanitize_string(
            alert_id, max_length=100, field_name="alert ID"
        )
    except ValueError as e:
        return f"Invalid alert ID: {e}"

    client = get_client()
    try:
        await client.delete_news_alert(alert_id)
        return f"News alert {alert_id} deleted successfully."
    except Exception as e:
        logger.error("Failed to delete alert %s: %s", alert_id, e)
        return f"Failed to delete alert: {e}"
