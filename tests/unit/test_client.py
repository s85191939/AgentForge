"""Unit tests for the GhostfolioClient."""

from __future__ import annotations

import pytest
import httpx
import respx

from agent.core.client import GhostfolioClient


@pytest.fixture
def client():
    return GhostfolioClient(
        base_url="http://localhost:3333",
        security_token="test-token",
    )


@respx.mock
@pytest.mark.asyncio
async def test_authenticate(client: GhostfolioClient):
    """Test that authenticate exchanges the security token for a JWT."""
    respx.post("http://localhost:3333/api/v1/auth/anonymous").mock(
        return_value=httpx.Response(200, json={"authToken": "jwt-abc-123"})
    )

    jwt = await client.authenticate()
    assert jwt == "jwt-abc-123"
    assert client._jwt == "jwt-abc-123"


@respx.mock
@pytest.mark.asyncio
async def test_health_check(client: GhostfolioClient):
    """Test the health check endpoint."""
    respx.get("http://localhost:3333/api/v1/health").mock(
        return_value=httpx.Response(200, json={"status": "OK"})
    )

    result = await client.health_check()
    assert result == {"status": "OK"}


@respx.mock
@pytest.mark.asyncio
async def test_auto_authenticates_on_first_request(client: GhostfolioClient):
    """Test that calling an endpoint without prior auth triggers auto-auth."""
    respx.post("http://localhost:3333/api/v1/auth/anonymous").mock(
        return_value=httpx.Response(200, json={"authToken": "jwt-auto"})
    )
    respx.get("http://localhost:3333/api/v1/portfolio/holdings").mock(
        return_value=httpx.Response(200, json={"holdings": []})
    )

    # No explicit authenticate() call — should auto-auth
    result = await client.get_portfolio_holdings()
    assert client._jwt == "jwt-auto"
    assert "holdings" in result


@respx.mock
@pytest.mark.asyncio
async def test_reauth_on_401(client: GhostfolioClient):
    """Test that a 401 response triggers re-authentication and retry."""
    # First auth
    respx.post("http://localhost:3333/api/v1/auth/anonymous").mock(
        return_value=httpx.Response(200, json={"authToken": "jwt-new"})
    )

    # First GET returns 401, second GET (after re-auth) returns 200
    holdings_route = respx.get("http://localhost:3333/api/v1/portfolio/holdings")
    holdings_route.side_effect = [
        httpx.Response(401, json={"message": "Unauthorized"}),
        httpx.Response(200, json={"holdings": [{"symbol": "AAPL"}]}),
    ]

    result = await client.get_portfolio_holdings()
    assert result["holdings"][0]["symbol"] == "AAPL"


@respx.mock
@pytest.mark.asyncio
async def test_get_portfolio_holdings(client: GhostfolioClient):
    """Test fetching portfolio holdings (with explicit pre-auth)."""
    respx.post("http://localhost:3333/api/v1/auth/anonymous").mock(
        return_value=httpx.Response(200, json={"authToken": "jwt-test"})
    )
    await client.authenticate()

    mock_holdings = {
        "holdings": [
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "marketValue": 15000,
                "currency": "USD",
                "allocationInPercentage": 30,
                "assetClass": "EQUITY",
                "assetSubClass": "STOCK",
            }
        ]
    }
    respx.get("http://localhost:3333/api/v1/portfolio/holdings").mock(
        return_value=httpx.Response(200, json=mock_holdings)
    )

    result = await client.get_portfolio_holdings()
    assert "holdings" in result
    assert result["holdings"][0]["symbol"] == "AAPL"


@respx.mock
@pytest.mark.asyncio
async def test_get_portfolio_performance(client: GhostfolioClient):
    """Test fetching portfolio performance."""
    respx.post("http://localhost:3333/api/v1/auth/anonymous").mock(
        return_value=httpx.Response(200, json={"authToken": "jwt-test"})
    )
    await client.authenticate()

    mock_perf = {
        "currentValue": 50000,
        "netPerformance": 5000,
        "netPerformancePercentage": 0.1,
        "totalInvestment": 45000,
    }
    respx.get("http://localhost:3333/api/v2/portfolio/performance").mock(
        return_value=httpx.Response(200, json=mock_perf)
    )

    result = await client.get_portfolio_performance(range_="ytd")
    assert result["currentValue"] == 50000
    assert result["netPerformancePercentage"] == 0.1


@respx.mock
@pytest.mark.asyncio
async def test_lookup_symbol(client: GhostfolioClient):
    """Test symbol lookup."""
    respx.post("http://localhost:3333/api/v1/auth/anonymous").mock(
        return_value=httpx.Response(200, json={"authToken": "jwt-test"})
    )
    await client.authenticate()

    mock_results = {
        "items": [
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "assetClass": "EQUITY",
                "assetSubClass": "STOCK",
                "dataSource": "YAHOO",
                "currency": "USD",
            }
        ]
    }
    respx.get("http://localhost:3333/api/v1/symbol/lookup").mock(
        return_value=httpx.Response(200, json=mock_results)
    )

    result = await client.lookup_symbol("AAPL")
    assert result["items"][0]["symbol"] == "AAPL"


@respx.mock
@pytest.mark.asyncio
async def test_import_activities(client: GhostfolioClient):
    """Test importing activities."""
    respx.post("http://localhost:3333/api/v1/auth/anonymous").mock(
        return_value=httpx.Response(200, json={"authToken": "jwt-test"})
    )
    await client.authenticate()

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
    result = await client.import_activities(activities)
    assert "activities" in result
