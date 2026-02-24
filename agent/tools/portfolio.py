"""Portfolio analysis tools — holdings, performance, details."""

from __future__ import annotations

import json

from langchain_core.tools import tool

from agent.tools.auth import get_client


@tool
async def get_portfolio_holdings() -> str:
    """Retrieve current portfolio holdings with market values.

    Returns all positions the user currently holds, including:
    - Symbol and name
    - Asset class and sub-class
    - Quantity and current market value
    - Currency and allocation percentage

    Use this when the user asks about what they own, their positions,
    or wants a breakdown of their portfolio.
    """
    client = get_client()
    data = await client.get_portfolio_holdings()
    holdings = data if isinstance(data, list) else data.get("holdings", data)

    if not holdings:
        return "No holdings found in the portfolio."

    # Summarise for the LLM — keep it structured but concise
    summary_lines: list[str] = []
    for h in holdings if isinstance(holdings, list) else [holdings]:
        name = h.get("name", h.get("symbol", "Unknown"))
        symbol = h.get("symbol", "")
        quantity = h.get("quantity", "N/A")
        market_price = h.get("marketPrice", "N/A")
        value = h.get("valueInBaseCurrency", h.get("marketValue", h.get("value", "N/A")))
        currency = h.get("currency", "")
        allocation = h.get("allocationInPercentage", "N/A")
        asset_class = h.get("assetClass", "")
        asset_sub_class = h.get("assetSubClass", "")
        perf_pct = h.get("netPerformancePercent", None)
        perf_str = f" | Performance: {perf_pct * 100:.2f}%" if perf_pct is not None else ""
        summary_lines.append(
            f"- {name} ({symbol}): Price: {currency} {market_price} | "
            f"Qty: {quantity} | Value: {currency} {value} | "
            f"Allocation: {allocation}% | "
            f"Class: {asset_class}/{asset_sub_class}{perf_str}"
        )

    return f"Portfolio Holdings ({len(summary_lines)} positions):\n" + "\n".join(summary_lines)


@tool
async def get_portfolio_performance(range: str = "max") -> str:
    """Get portfolio performance metrics for a given time range.

    Args:
        range: Time range for performance calculation. Options:
            1d, wtd, 1w, mtd, 1m, 3m, ytd, 1y, 3y, 5y, max

    Returns performance data including:
    - Total return (absolute and percentage)
    - Current net worth
    - Gross/net performance

    Use this when the user asks how their portfolio has performed,
    returns over a period, or gains/losses.
    """
    client = get_client()
    data = await client.get_portfolio_performance(range_=range)

    perf = data if isinstance(data, dict) else {}
    current_value = perf.get("currentValue", "N/A")
    net_perf = perf.get("netPerformance", "N/A")
    net_perf_pct = perf.get("netPerformancePercentage", "N/A")
    gross_perf = perf.get("grossPerformance", "N/A")
    gross_perf_pct = perf.get("grossPerformancePercentage", "N/A")
    total_investment = perf.get("totalInvestment", "N/A")

    if net_perf_pct != "N/A" and isinstance(net_perf_pct, (int, float)):
        net_perf_pct = f"{net_perf_pct * 100:.2f}%"
    if gross_perf_pct != "N/A" and isinstance(gross_perf_pct, (int, float)):
        gross_perf_pct = f"{gross_perf_pct * 100:.2f}%"

    return (
        f"Portfolio Performance (range: {range}):\n"
        f"- Current Value: {current_value}\n"
        f"- Total Invested: {total_investment}\n"
        f"- Net Performance: {net_perf} ({net_perf_pct})\n"
        f"- Gross Performance: {gross_perf} ({gross_perf_pct})"
    )


@tool
async def get_portfolio_details(range: str = "max") -> str:
    """Get detailed portfolio breakdown including allocation by asset class,
    sector, region, and account.

    Args:
        range: Time range. Options: 1d, wtd, 1w, mtd, 1m, 3m, ytd, 1y, 3y, 5y, max

    Returns comprehensive portfolio details including:
    - Holdings with full metadata
    - Allocation by asset class, sector, region
    - Account breakdown

    Use this when the user asks about diversification, asset allocation,
    sector exposure, geographic distribution, or concentration analysis.
    """
    client = get_client()
    data = await client.get_portfolio_details(range_=range)

    # Return the raw JSON but truncated if very large
    raw = json.dumps(data, indent=2, default=str)
    if len(raw) > 8000:
        return raw[:8000] + "\n\n... (truncated — full data available)"
    return f"Portfolio Details (range: {range}):\n{raw}"
