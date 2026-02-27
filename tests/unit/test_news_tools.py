"""Unit tests for news and alert tool wrappers."""

from __future__ import annotations

import httpx
import pytest
import respx

from agent.core.client import GhostfolioClient
from agent.tools.auth import set_client
from agent.tools.news import (
    create_news_alert,
    delete_news_alert,
    get_portfolio_news,
    get_symbol_news,
    list_news_alerts,
    update_news_alert,
)


@pytest.fixture(autouse=True)
def setup_client():
    """Create and register a mock client for all news tool tests."""
    client = GhostfolioClient(
        base_url="http://localhost:3333",
        security_token="test-token",
    )
    set_client(client)
    return client


def _mock_auth():
    """Mock the authentication endpoint."""
    respx.post("http://localhost:3333/api/v1/auth/anonymous").mock(
        return_value=httpx.Response(200, json={"authToken": "jwt-test"})
    )


# ---------------------------------------------------------------------------
# get_portfolio_news
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_get_portfolio_news_with_articles(setup_client):
    _mock_auth()
    await setup_client.authenticate()

    respx.get("http://localhost:3333/api/v1/news/portfolio").mock(
        return_value=httpx.Response(200, json={
            "articles": [
                {
                    "symbol": "AAPL",
                    "headline": "Apple reports record revenue",
                    "source": "Reuters",
                    "sentiment": "positive",
                    "published_at": "2024-06-15T10:00:00Z",
                },
                {
                    "symbol": "MSFT",
                    "headline": "Microsoft cloud growth slows",
                    "source": "Bloomberg",
                    "sentiment": "negative",
                    "published_at": "2024-06-14T08:00:00Z",
                },
            ],
            "symbols": ["AAPL", "MSFT"],
        })
    )

    result = await get_portfolio_news.ainvoke({})
    assert "Portfolio News" in result
    assert "AAPL" in result
    assert "Apple reports record revenue" in result
    assert "[+]" in result  # positive sentiment icon
    assert "[-]" in result  # negative sentiment icon


@respx.mock
@pytest.mark.asyncio
async def test_get_portfolio_news_empty(setup_client):
    _mock_auth()
    await setup_client.authenticate()

    respx.get("http://localhost:3333/api/v1/news/portfolio").mock(
        return_value=httpx.Response(200, json={
            "articles": [],
            "symbols": ["AAPL"],
        })
    )

    result = await get_portfolio_news.ainvoke({})
    assert "No recent news" in result


@respx.mock
@pytest.mark.asyncio
async def test_get_portfolio_news_error(setup_client):
    _mock_auth()
    await setup_client.authenticate()

    respx.get("http://localhost:3333/api/v1/news/portfolio").mock(
        return_value=httpx.Response(500)
    )

    result = await get_portfolio_news.ainvoke({})
    assert "Unable to fetch" in result


# ---------------------------------------------------------------------------
# get_symbol_news
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_get_symbol_news_with_articles(setup_client):
    _mock_auth()
    await setup_client.authenticate()

    respx.get("http://localhost:3333/api/v1/news").mock(
        return_value=httpx.Response(200, json={
            "articles": [
                {
                    "headline": "Tesla delivers record vehicles",
                    "source": "CNBC",
                    "sentiment": "positive",
                    "published_at": "2024-06-15T12:00:00Z",
                },
            ],
        })
    )

    result = await get_symbol_news.ainvoke({"symbol": "TSLA"})
    assert "News for TSLA" in result
    assert "Tesla delivers record vehicles" in result


@respx.mock
@pytest.mark.asyncio
async def test_get_symbol_news_empty(setup_client):
    _mock_auth()
    await setup_client.authenticate()

    respx.get("http://localhost:3333/api/v1/news").mock(
        return_value=httpx.Response(200, json={"articles": []})
    )

    result = await get_symbol_news.ainvoke({"symbol": "XYZ"})
    assert "No recent news" in result


@pytest.mark.asyncio
async def test_get_symbol_news_invalid_symbol():
    result = await get_symbol_news.ainvoke({"symbol": "   "})
    assert "Invalid symbol" in result


# ---------------------------------------------------------------------------
# create_news_alert
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_create_news_alert_success(setup_client):
    _mock_auth()
    await setup_client.authenticate()

    respx.post("http://localhost:3333/api/v1/news/alerts").mock(
        return_value=httpx.Response(201, json={
            "id": "alert-uuid-123",
            "symbol": "AAPL",
            "keywords": "earnings",
        })
    )

    result = await create_news_alert.ainvoke({
        "symbol": "AAPL",
        "keywords": "earnings",
    })
    assert "News alert created for AAPL" in result
    assert "alert-uuid-123" in result
    assert "earnings" in result


@respx.mock
@pytest.mark.asyncio
async def test_create_news_alert_no_keywords(setup_client):
    _mock_auth()
    await setup_client.authenticate()

    respx.post("http://localhost:3333/api/v1/news/alerts").mock(
        return_value=httpx.Response(201, json={
            "id": "alert-uuid-456",
            "symbol": "MSFT",
        })
    )

    result = await create_news_alert.ainvoke({"symbol": "MSFT"})
    assert "News alert created for MSFT" in result
    assert "keywords" not in result.lower().split("alert id")[0]


@pytest.mark.asyncio
async def test_create_news_alert_invalid_symbol():
    result = await create_news_alert.ainvoke({"symbol": "   "})
    assert "Invalid symbol" in result


# ---------------------------------------------------------------------------
# list_news_alerts
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_list_news_alerts_with_alerts(setup_client):
    _mock_auth()
    await setup_client.authenticate()

    respx.get("http://localhost:3333/api/v1/news/alerts").mock(
        return_value=httpx.Response(200, json=[
            {
                "id": "alert-1",
                "symbol": "AAPL",
                "keywords": "earnings",
                "is_active": True,
            },
            {
                "id": "alert-2",
                "symbol": "TSLA",
                "keywords": "",
                "is_active": False,
            },
        ])
    )

    result = await list_news_alerts.ainvoke({})
    assert "News Alerts (2)" in result
    assert "AAPL" in result
    assert "TSLA" in result
    assert "Active" in result
    assert "Paused" in result


@respx.mock
@pytest.mark.asyncio
async def test_list_news_alerts_empty(setup_client):
    _mock_auth()
    await setup_client.authenticate()

    respx.get("http://localhost:3333/api/v1/news/alerts").mock(
        return_value=httpx.Response(200, json=[])
    )

    result = await list_news_alerts.ainvoke({})
    assert "No news alerts" in result


# ---------------------------------------------------------------------------
# update_news_alert
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_update_news_alert_success(setup_client):
    _mock_auth()
    await setup_client.authenticate()

    respx.patch("http://localhost:3333/api/v1/news/alerts/alert-1").mock(
        return_value=httpx.Response(200, json={
            "id": "alert-1",
            "symbol": "AAPL",
            "keywords": "dividend",
            "is_active": True,
        })
    )

    result = await update_news_alert.ainvoke({
        "alert_id": "alert-1",
        "keywords": "dividend",
        "is_active": True,
    })
    assert "updated successfully" in result
    assert "active" in result
    assert "dividend" in result


@respx.mock
@pytest.mark.asyncio
async def test_update_news_alert_pause(setup_client):
    _mock_auth()
    await setup_client.authenticate()

    respx.patch("http://localhost:3333/api/v1/news/alerts/alert-1").mock(
        return_value=httpx.Response(200, json={
            "id": "alert-1",
            "symbol": "AAPL",
            "is_active": False,
        })
    )

    result = await update_news_alert.ainvoke({
        "alert_id": "alert-1",
        "is_active": False,
    })
    assert "paused" in result


@pytest.mark.asyncio
async def test_update_news_alert_invalid_id():
    result = await update_news_alert.ainvoke({"alert_id": "   "})
    assert "Invalid alert ID" in result


# ---------------------------------------------------------------------------
# delete_news_alert
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_delete_news_alert_success(setup_client):
    _mock_auth()
    await setup_client.authenticate()

    respx.delete("http://localhost:3333/api/v1/news/alerts/alert-1").mock(
        return_value=httpx.Response(204)
    )

    result = await delete_news_alert.ainvoke({"alert_id": "alert-1"})
    assert "deleted successfully" in result


@respx.mock
@pytest.mark.asyncio
async def test_delete_news_alert_failure(setup_client):
    _mock_auth()
    await setup_client.authenticate()

    respx.delete("http://localhost:3333/api/v1/news/alerts/bad-id").mock(
        return_value=httpx.Response(404)
    )

    result = await delete_news_alert.ainvoke({"alert_id": "bad-id"})
    assert "Failed to delete" in result


@pytest.mark.asyncio
async def test_delete_news_alert_invalid_id():
    result = await delete_news_alert.ainvoke({"alert_id": "   "})
    assert "Invalid alert ID" in result
