"""User settings tools."""

from __future__ import annotations

import json
from langchain_core.tools import tool

from agent.tools.auth import get_client


@tool
async def get_user_settings() -> str:
    """Retrieve the current user's profile and settings.

    Returns:
    - User ID and role
    - Base currency preference
    - Date format and locale
    - Subscription status
    - Feature permissions

    Use this to understand user preferences (e.g., base currency)
    before performing analysis, or when the user asks about their settings.
    """
    client = get_client()
    data = await client.get_user()

    settings = data.get("settings", {})
    base_currency = settings.get("baseCurrency", "N/A")
    date_range = settings.get("dateRange", "N/A")
    locale = settings.get("locale", "N/A")

    subscription = data.get("subscription", {})
    sub_type = subscription.get("type", "N/A") if subscription else "N/A"

    return (
        f"User Settings:\n"
        f"- Base Currency: {base_currency}\n"
        f"- Default Date Range: {date_range}\n"
        f"- Locale: {locale}\n"
        f"- Subscription: {sub_type}"
    )
