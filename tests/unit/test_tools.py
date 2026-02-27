"""Unit tests for LangChain tool wrappers."""

from __future__ import annotations

import httpx
import pytest
import respx

from agent.core.client import GhostfolioClient
from agent.tools.accounts import get_accounts
from agent.tools.auth import set_client
from agent.tools.orders import delete_order, get_orders, import_activities, preview_import
from agent.tools.portfolio import (
    get_portfolio_details,
    get_portfolio_holdings,
    get_portfolio_performance,
)
from agent.tools.symbols import lookup_symbol
from agent.tools.user import get_user_settings


@pytest.fixture(autouse=True)
def setup_client():
    """Create and register a mock client for all tool tests."""
    client = GhostfolioClient(
        base_url="http://localhost:3333",
        security_token="test-token",
    )
    set_client(client)
    return client


@respx.mock
@pytest.mark.asyncio
async def test_get_portfolio_holdings_tool(setup_client):
    respx.post("http://localhost:3333/api/v1/auth/anonymous").mock(
        return_value=httpx.Response(200, json={"authToken": "jwt-test"})
    )
    await setup_client.authenticate()

    respx.get("http://localhost:3333/api/v1/portfolio/holdings").mock(
        return_value=httpx.Response(
            200,
            json={
                "holdings": [
                    {
                        "symbol": "MSFT",
                        "name": "Microsoft Corp",
                        "marketValue": 20000,
                        "currency": "USD",
                        "allocationInPercentage": 40,
                        "assetClass": "EQUITY",
                        "assetSubClass": "STOCK",
                    }
                ]
            },
        )
    )

    result = await get_portfolio_holdings.ainvoke({})
    assert "MSFT" in result
    assert "Microsoft" in result
    assert "40" in result


@respx.mock
@pytest.mark.asyncio
async def test_get_portfolio_performance_tool(setup_client):
    respx.post("http://localhost:3333/api/v1/auth/anonymous").mock(
        return_value=httpx.Response(200, json={"authToken": "jwt-test"})
    )
    await setup_client.authenticate()

    respx.get("http://localhost:3333/api/v2/portfolio/performance").mock(
        return_value=httpx.Response(
            200,
            json={
                "currentValue": 100000,
                "netPerformance": 10000,
                "netPerformancePercentage": 0.1,
                "grossPerformance": 11000,
                "grossPerformancePercentage": 0.11,
                "totalInvestment": 90000,
            },
        )
    )

    result = await get_portfolio_performance.ainvoke({"range": "ytd"})
    assert "100000" in result
    assert "10.00%" in result


@respx.mock
@pytest.mark.asyncio
async def test_get_orders_tool(setup_client):
    respx.post("http://localhost:3333/api/v1/auth/anonymous").mock(
        return_value=httpx.Response(200, json={"authToken": "jwt-test"})
    )
    await setup_client.authenticate()

    respx.get("http://localhost:3333/api/v1/order").mock(
        return_value=httpx.Response(
            200,
            json={
                "activities": [
                    {
                        "date": "2024-01-15T00:00:00.000Z",
                        "type": "BUY",
                        "symbol": "AAPL",
                        "quantity": 10,
                        "unitPrice": 185.50,
                        "currency": "USD",
                        "fee": 1.0,
                    }
                ]
            },
        )
    )

    result = await get_orders.ainvoke({})
    assert "BUY" in result
    assert "AAPL" in result


@respx.mock
@pytest.mark.asyncio
async def test_get_accounts_tool(setup_client):
    respx.post("http://localhost:3333/api/v1/auth/anonymous").mock(
        return_value=httpx.Response(200, json={"authToken": "jwt-test"})
    )
    await setup_client.authenticate()

    respx.get("http://localhost:3333/api/v1/account").mock(
        return_value=httpx.Response(
            200,
            json={
                "accounts": [
                    {
                        "name": "Brokerage",
                        "platformId": "interactive-brokers",
                        "balance": 5000,
                        "currency": "USD",
                        "value": 50000,
                        "isExcluded": False,
                    }
                ]
            },
        )
    )

    result = await get_accounts.ainvoke({})
    assert "Brokerage" in result
    assert "5000" in result


@respx.mock
@pytest.mark.asyncio
async def test_lookup_symbol_tool(setup_client):
    respx.post("http://localhost:3333/api/v1/auth/anonymous").mock(
        return_value=httpx.Response(200, json={"authToken": "jwt-test"})
    )
    await setup_client.authenticate()

    respx.get("http://localhost:3333/api/v1/symbol/lookup").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "symbol": "TSLA",
                        "name": "Tesla Inc",
                        "assetClass": "EQUITY",
                        "assetSubClass": "STOCK",
                        "dataSource": "YAHOO",
                        "currency": "USD",
                    }
                ]
            },
        )
    )

    result = await lookup_symbol.ainvoke({"query": "Tesla"})
    assert "TSLA" in result
    assert "Tesla" in result


@respx.mock
@pytest.mark.asyncio
async def test_get_user_settings_tool(setup_client):
    respx.post("http://localhost:3333/api/v1/auth/anonymous").mock(
        return_value=httpx.Response(200, json={"authToken": "jwt-test"})
    )
    await setup_client.authenticate()

    respx.get("http://localhost:3333/api/v1/user").mock(
        return_value=httpx.Response(
            200,
            json={
                "settings": {
                    "baseCurrency": "USD",
                    "dateRange": "max",
                    "locale": "en-US",
                },
                "subscription": {"type": "Premium"},
            },
        )
    )

    result = await get_user_settings.ainvoke({})
    assert "USD" in result
    assert "Premium" in result


# ---------------------------------------------------------------
# Import tool tests
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_import_valid():
    """preview_import returns a human-readable summary."""
    import json

    activities = [
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2024-01-15T00:00:00.000Z",
            "fee": 0,
            "quantity": 10,
            "symbol": "AAPL",
            "type": "BUY",
            "unitPrice": 185.50,
        }
    ]
    result = await preview_import.ainvoke({"activities_json": json.dumps(activities)})
    assert "Import Preview" in result
    assert "AAPL" in result
    assert "BUY" in result


@pytest.mark.asyncio
async def test_preview_import_invalid_json():
    """preview_import returns error on invalid JSON."""
    result = await preview_import.ainvoke({"activities_json": "not json"})
    assert "Error" in result


@pytest.mark.asyncio
async def test_preview_import_missing_fields():
    """preview_import returns error on missing required fields."""
    import json

    activities = [{"symbol": "AAPL", "type": "BUY"}]
    result = await preview_import.ainvoke({"activities_json": json.dumps(activities)})
    assert "missing required fields" in result


@pytest.mark.asyncio
async def test_import_activities_requires_confirmation():
    """import_activities refuses to execute without confirmed=True."""
    import json

    activities = [
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2024-01-15T00:00:00.000Z",
            "fee": 0,
            "quantity": 10,
            "symbol": "AAPL",
            "type": "BUY",
            "unitPrice": 185.50,
        }
    ]
    result = await import_activities.ainvoke({
        "activities_json": json.dumps(activities),
        "confirmed": False,
    })
    assert "NOT executed" in result


@respx.mock
@pytest.mark.asyncio
async def test_import_activities_confirmed(setup_client):
    """import_activities executes when confirmed=True."""
    import json

    respx.post("http://localhost:3333/api/v1/auth/anonymous").mock(
        return_value=httpx.Response(200, json={"authToken": "jwt-test"})
    )
    await setup_client.authenticate()

    respx.post("http://localhost:3333/api/v1/import").mock(
        return_value=httpx.Response(201, json={"activities": []})
    )

    activities = [
        {
            "currency": "USD",
            "dataSource": "YAHOO",
            "date": "2024-01-15T00:00:00.000Z",
            "fee": 0,
            "quantity": 10,
            "symbol": "AAPL",
            "type": "BUY",
            "unitPrice": 185.50,
        }
    ]
    result = await import_activities.ainvoke({
        "activities_json": json.dumps(activities),
        "confirmed": True,
    })
    assert "Successfully imported" in result


# ---------------------------------------------------------------
# delete_order tool tests
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_order_requires_confirmation():
    """delete_order refuses to execute without confirmed=True."""
    result = await delete_order.ainvoke({
        "order_id": "some-uuid-123",
        "confirmed": False,
    })
    assert "NOT executed" in result


@respx.mock
@pytest.mark.asyncio
async def test_delete_order_confirmed(setup_client):
    """delete_order executes when confirmed=True."""
    respx.post("http://localhost:3333/api/v1/auth/anonymous").mock(
        return_value=httpx.Response(200, json={"authToken": "jwt-test"})
    )
    await setup_client.authenticate()

    respx.delete("http://localhost:3333/api/v1/order/order-uuid-123").mock(
        return_value=httpx.Response(204)
    )

    result = await delete_order.ainvoke({
        "order_id": "order-uuid-123",
        "confirmed": True,
    })
    assert "Successfully deleted" in result
    assert "order-uuid-123" in result


@respx.mock
@pytest.mark.asyncio
async def test_delete_order_api_failure(setup_client):
    """delete_order returns error message on API failure."""
    respx.post("http://localhost:3333/api/v1/auth/anonymous").mock(
        return_value=httpx.Response(200, json={"authToken": "jwt-test"})
    )
    await setup_client.authenticate()

    respx.delete("http://localhost:3333/api/v1/order/bad-id").mock(
        return_value=httpx.Response(404)
    )

    result = await delete_order.ainvoke({
        "order_id": "bad-id",
        "confirmed": True,
    })
    assert "Failed to delete" in result


# ---------------------------------------------------------------
# get_portfolio_details tool tests
# ---------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_get_portfolio_details_tool(setup_client):
    """get_portfolio_details returns detailed breakdown."""
    respx.post("http://localhost:3333/api/v1/auth/anonymous").mock(
        return_value=httpx.Response(200, json={"authToken": "jwt-test"})
    )
    await setup_client.authenticate()

    mock_details = {
        "holdings": [
            {
                "symbol": "AAPL",
                "name": "Apple Inc",
                "allocationInPercentage": 0.5,
                "assetClass": "EQUITY",
                "sectors": [{"name": "Technology", "weight": 1.0}],
                "countries": [{"code": "US", "weight": 1.0}],
            }
        ],
        "summary": {
            "cash": 5000,
            "committedFunds": 0,
        },
    }
    respx.get("http://localhost:3333/api/v1/portfolio/details").mock(
        return_value=httpx.Response(200, json=mock_details)
    )

    result = await get_portfolio_details.ainvoke({"range": "max"})
    assert "Portfolio Details" in result
    assert "AAPL" in result


@pytest.mark.asyncio
async def test_get_portfolio_details_invalid_range():
    """get_portfolio_details returns error on invalid range."""
    result = await get_portfolio_details.ainvoke({"range": "invalid"})
    assert "Invalid range" in result
