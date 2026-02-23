"""Account management tools."""

from __future__ import annotations

from langchain_core.tools import tool

from agent.tools.auth import get_client


@tool
async def get_accounts() -> str:
    """Retrieve all investment accounts.

    Returns account information including:
    - Account name and ID
    - Platform (broker)
    - Balance and currency
    - Whether it is excluded from analysis

    Use this when the user asks about their accounts, brokers,
    or where their money is held.
    """
    client = get_client()
    data = await client.get_accounts()
    accounts = data if isinstance(data, list) else data.get("accounts", data)

    if not accounts:
        return "No accounts found."

    summary_lines: list[str] = []
    for acc in accounts if isinstance(accounts, list) else [accounts]:
        name = acc.get("name", "Unknown")
        platform = acc.get("Platform", {}).get("name", acc.get("platformId", "N/A"))
        balance = acc.get("balance", 0)
        currency = acc.get("currency", "")
        value = acc.get("value", "N/A")
        excluded = acc.get("isExcluded", False)
        summary_lines.append(
            f"- {name} ({platform}): Balance {currency} {balance} | "
            f"Value: {currency} {value} | Excluded: {excluded}"
        )

    return f"Accounts ({len(summary_lines)}):\n" + "\n".join(summary_lines)
