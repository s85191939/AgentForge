"""Symbol / market data lookup tools."""

from __future__ import annotations

from langchain_core.tools import tool

from agent.core.validators import validate_symbol_query
from agent.tools.auth import get_client


@tool
async def lookup_symbol(query: str) -> str:
    """Search for a financial instrument by name or ticker symbol.

    Args:
        query: Search term — can be a ticker (e.g., "AAPL"), ISIN,
               or partial name (e.g., "Apple").

    Returns matching symbols with:
    - Symbol/ticker
    - Name
    - Asset class and sub-class
    - Data source
    - Currency

    IMPORTANT: This tool does NOT return the current market price.
    For prices, use get_portfolio_holdings instead (which includes
    marketPrice for all positions in the portfolio).

    Use this when the user mentions a stock, ETF, crypto, or other
    asset and you need to look up its details or verify it exists
    in Ghostfolio's data sources.
    """
    try:
        query = validate_symbol_query(query)
    except ValueError as e:
        return f"Invalid symbol query: {e}"

    client = get_client()
    data = await client.lookup_symbol(query)
    items = data if isinstance(data, list) else data.get("items", data)

    if not items:
        return f"No results found for '{query}'."

    summary_lines: list[str] = []
    for item in items if isinstance(items, list) else [items]:
        symbol = item.get("symbol", "N/A")
        name = item.get("name", "N/A")
        asset_class = item.get("assetClass", "")
        asset_sub_class = item.get("assetSubClass", "")
        data_source = item.get("dataSource", "")
        currency = item.get("currency", "")
        summary_lines.append(
            f"- {symbol} | {name} | {asset_class}/{asset_sub_class} | "
            f"Source: {data_source} | {currency}"
        )

    return (
        f"Symbol lookup results for '{query}' ({len(summary_lines)} found):\n"
        + "\n".join(summary_lines[:20])
    )
