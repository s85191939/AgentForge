"""Transaction / activity tools — read, preview, import, and delete orders."""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from agent.core.validators import sanitize_string, validate_json_payload
from agent.tools.auth import get_client

logger = logging.getLogger("agentforge.tools.orders")

# Known trading currencies for popular tickers (extend as needed)
_SYMBOL_CURRENCIES: dict[str, str] = {
    "AAPL": "USD", "MSFT": "USD", "GOOGL": "USD", "AMZN": "USD",
    "NVDA": "USD", "TSLA": "USD", "META": "USD", "BRK.B": "USD",
    "VTI": "USD", "VOO": "USD", "SPY": "USD", "QQQ": "USD",
    "BND": "USD", "VXUS": "USD", "IVV": "USD", "AGG": "USD",
}


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
        order_id = o.get("id", "N/A")
        date = o.get("date", "N/A")[:10]
        type_ = o.get("type", "N/A")
        symbol = o.get("SymbolProfile", {}).get("symbol", o.get("symbol", "N/A"))
        qty = o.get("quantity", "N/A")
        price = o.get("unitPrice", "N/A")
        currency = o.get("SymbolProfile", {}).get("currency", o.get("currency", ""))
        txn_currency = o.get("currency", "")
        fee = o.get("fee", 0)
        currency_note = ""
        if txn_currency and txn_currency != currency:
            currency_note = f" [TXN CURRENCY: {txn_currency}]"
        summary_lines.append(
            f"- ID: {order_id} | {date} | {type_:>8} | {symbol:<8} "
            f"| Qty: {qty} @ {currency} {price} | Fee: {fee}{currency_note}"
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
    warnings: list[str] = []
    for i, act in enumerate(activities):
        symbol = act["symbol"].upper()
        currency = act["currency"].upper()
        lines.append(
            f"  {i + 1}. {act['type']} {act['quantity']} {symbol} "
            f"@ {currency} {act['unitPrice']} on {act['date'][:10]} "
            f"(fee: {act['fee']}, source: {act['dataSource']})"
        )
        # Currency mismatch check — prevents Ghostfolio 500 errors
        expected = _SYMBOL_CURRENCIES.get(symbol)
        if expected and currency != expected:
            warnings.append(
                f"  WARNING: {symbol} normally trades in {expected}, but you "
                f"specified {currency}. This WILL cause portfolio calculation "
                f"errors in Ghostfolio. Please use {expected} instead."
            )

    result = (
        f"Import Preview — {len(activities)} activit{'y' if len(activities) == 1 else 'ies'}:\n"
        + "\n".join(lines)
    )
    if warnings:
        result += "\n\n CURRENCY MISMATCH DETECTED:\n" + "\n".join(warnings)
        result += "\n\nDo NOT proceed with this import. Ask the user to correct the currency."
    else:
        result += (
            "\n\nAsk the user to confirm before calling "
            "import_activities with confirmed=True."
        )

    return result


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


@tool
async def delete_order(order_id: str, confirmed: bool = False) -> str:
    """Delete a single transaction/activity from Ghostfolio by its ID.

    Args:
        order_id: The UUID of the order/activity to delete.
            Get order IDs from the get_orders tool output.
        confirmed: Must be True to execute. Set to True only AFTER the user
            has reviewed which order will be deleted and explicitly approved.

    IMPORTANT: Always show the user which transaction will be deleted
    (using get_orders to find it) and get explicit confirmation before
    calling this with confirmed=True.
    """
    if not confirmed:
        return (
            "Deletion NOT executed — confirmed must be True. "
            "Please show the user which transaction will be deleted "
            "and only call delete_order with confirmed=True after they approve."
        )

    try:
        order_id = sanitize_string(order_id, max_length=100, field_name="order ID")
    except ValueError as e:
        return f"Invalid order ID: {e}"

    client = get_client()
    try:
        await client.delete_order(order_id)
        return f"Successfully deleted order {order_id}."
    except Exception as e:
        logger.error("Failed to delete order %s: %s", order_id, e)
        return f"Failed to delete order: {e}"
