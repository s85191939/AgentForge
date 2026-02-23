"""Transaction / activity tools — read and import orders."""

from __future__ import annotations

import json
from langchain_core.tools import tool

from agent.tools.auth import get_client


@tool
async def get_orders() -> str:
    """Retrieve the full transaction history (activities/orders).

    Returns all recorded activities including:
    - BUY, SELL, DIVIDEND, INTEREST, FEE, LIABILITY
    - Date, symbol, quantity, unit price, fee, currency

    Use this when the user asks about their transaction history,
    past trades, dividend income, or fee analysis.
    """
    client = get_client()
    data = await client.get_orders()
    orders = data if isinstance(data, list) else data.get("activities", data)

    if not orders:
        return "No transactions found."

    summary_lines: list[str] = []
    for o in orders if isinstance(orders, list) else [orders]:
        date = o.get("date", "N/A")[:10]
        type_ = o.get("type", "N/A")
        symbol = o.get("SymbolProfile", {}).get("symbol", o.get("symbol", "N/A"))
        qty = o.get("quantity", "N/A")
        price = o.get("unitPrice", "N/A")
        currency = o.get("SymbolProfile", {}).get("currency", o.get("currency", ""))
        fee = o.get("fee", 0)
        summary_lines.append(
            f"- {date} | {type_:>8} | {symbol:<8} | Qty: {qty} @ {currency} {price} | Fee: {fee}"
        )

    return (
        f"Transaction History ({len(summary_lines)} activities):\n"
        + "\n".join(summary_lines[-50:])  # Last 50 for brevity
        + (f"\n\n(Showing last 50 of {len(summary_lines)})" if len(summary_lines) > 50 else "")
    )


@tool
async def import_activities(activities_json: str) -> str:
    """Import new transactions/activities into Ghostfolio.

    Args:
        activities_json: A JSON string containing a list of activity objects.
            Each activity must have:
            - currency (str): e.g., "USD"
            - dataSource (str): e.g., "YAHOO"
            - date (str): ISO 8601 date, e.g., "2024-01-01T00:00:00.000Z"
            - fee (float): Transaction fee
            - quantity (float): Number of units
            - symbol (str): Ticker symbol, e.g., "AAPL"
            - type (str): One of BUY, SELL, DIVIDEND, INTEREST, FEE, LIABILITY
            - unitPrice (float): Price per unit

    Use this when the user wants to record a new transaction.
    Always confirm with the user before importing.
    """
    try:
        activities = json.loads(activities_json)
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON — {e}"

    if not isinstance(activities, list):
        activities = [activities]

    # Validate required fields
    required = {"currency", "dataSource", "date", "fee", "quantity", "symbol", "type", "unitPrice"}
    for i, act in enumerate(activities):
        missing = required - set(act.keys())
        if missing:
            return f"Error: Activity {i} is missing required fields: {missing}"

    client = get_client()
    result = await client.import_activities(activities)
    count = len(activities)
    return f"Successfully imported {count} activit{'y' if count == 1 else 'ies'}."
