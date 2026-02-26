"""Transaction / activity tools — read, preview, and import orders."""

from __future__ import annotations

import json

from langchain_core.tools import tool

from agent.core.validators import validate_json_payload
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


def _validate_activities(activities_json: str) -> tuple[list[dict] | None, str | None]:
    """Parse and validate activities JSON. Returns (activities, error_message)."""
    try:
        activities_json = validate_json_payload(activities_json, "activities JSON")
    except ValueError as e:
        return None, f"Error: {e}"

    try:
        activities = json.loads(activities_json)
    except json.JSONDecodeError as e:
        return None, f"Error: Invalid JSON — {e}"

    if not isinstance(activities, list):
        activities = [activities]

    required = {"currency", "dataSource", "date", "fee", "quantity", "symbol", "type", "unitPrice"}
    for i, act in enumerate(activities):
        missing = required - set(act.keys())
        if missing:
            return None, f"Error: Activity {i} is missing required fields: {missing}"

    return activities, None


@tool
async def preview_import(activities_json: str) -> str:
    """Validate and preview activities before importing. Call this FIRST before import_activities.

    Args:
        activities_json: A JSON string containing a list of activity objects.
            Each activity must have: currency, dataSource, date, fee, quantity,
            symbol, type, unitPrice.

    Returns a summary of what will be imported so the user can confirm.
    Use this to show the user what will be imported before they approve.
    """
    activities, error = _validate_activities(activities_json)
    if error:
        return error

    assert activities is not None
    lines: list[str] = []
    for i, act in enumerate(activities):
        lines.append(
            f"  {i + 1}. {act['type']} {act['quantity']} {act['symbol']} "
            f"@ {act['currency']} {act['unitPrice']} on {act['date'][:10]} "
            f"(fee: {act['fee']}, source: {act['dataSource']})"
        )

    return (
        f"Import Preview — {len(activities)} activit{'y' if len(activities) == 1 else 'ies'}:\n"
        + "\n".join(lines)
        + "\n\nAsk the user to confirm before calling import_activities with confirmed=True."
    )


@tool
async def import_activities(activities_json: str, confirmed: bool = False) -> str:
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
        confirmed: Must be True to execute. Set to True only AFTER the user
            has reviewed the preview_import output and explicitly approved.

    IMPORTANT: Always call preview_import first and get user confirmation
    before calling this with confirmed=True.
    """
    if not confirmed:
        return (
            "Import NOT executed — confirmed must be True. "
            "Please call preview_import first, show the summary to the user, "
            "and only call import_activities with confirmed=True after they approve."
        )

    activities, error = _validate_activities(activities_json)
    if error:
        return error

    assert activities is not None
    client = get_client()
    await client.import_activities(activities)
    count = len(activities)
    return f"Successfully imported {count} activit{'y' if count == 1 else 'ies'}."
