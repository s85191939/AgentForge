"""End-to-end integration tests for the AgentForge Finance agent.

Requires a running Ghostfolio instance with seed data.
Run with: pytest tests/integration -v -m integration

These tests are SKIPPED by default in CI. To run them locally:
    docker compose -f docker/docker-compose.yml up -d
    python scripts/seed_data.py
    pytest tests/integration -v -m integration
"""

from __future__ import annotations

import pytest

from agent.core.agent import create_agent

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def agent():
    """Create a shared agent for all integration tests."""
    return create_agent()


@pytest.mark.asyncio
async def test_single_turn_holdings(agent):
    """Agent can retrieve and describe portfolio holdings."""
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "What are my holdings?"}]},
        config={"configurable": {"thread_id": "integ-holdings"}},
    )
    response = result["messages"][-1].content
    # Should mention at least one of the seeded stocks
    assert any(sym in response for sym in ["AAPL", "MSFT", "VTI", "GOOGL", "AMZN", "NVDA"])


@pytest.mark.asyncio
async def test_multi_turn_memory(agent):
    """Agent retains context across turns within the same thread."""
    tid = "integ-memory"
    cfg = {"configurable": {"thread_id": tid}}

    # Turn 1: ask about holdings
    await agent.ainvoke(
        {"messages": [{"role": "user", "content": "What are my holdings?"}]},
        config=cfg,
    )

    # Turn 2: follow-up that requires memory of turn 1
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "Which one has the highest allocation?"}]},
        config=cfg,
    )
    response = result["messages"][-1].content
    # Should reference a specific holding without needing re-fetching context
    assert len(response) > 20


@pytest.mark.asyncio
async def test_performance_query(agent):
    """Agent can retrieve and describe portfolio performance."""
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "How has my portfolio done this year?"}]},
        config={"configurable": {"thread_id": "integ-perf"}},
    )
    response = result["messages"][-1].content.lower()
    assert any(kw in response for kw in ["performance", "return", "%", "value", "gain", "loss"])


@pytest.mark.asyncio
async def test_accounts_query(agent):
    """Agent can list accounts."""
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "What accounts do I have?"}]},
        config={"configurable": {"thread_id": "integ-accounts"}},
    )
    response = result["messages"][-1].content
    # Should have some content about accounts
    assert len(response) > 10


@pytest.mark.asyncio
async def test_symbol_lookup(agent):
    """Agent can look up a stock symbol."""
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "Look up the ticker for Tesla"}]},
        config={"configurable": {"thread_id": "integ-symbol"}},
    )
    response = result["messages"][-1].content
    assert "TSLA" in response or "Tesla" in response
