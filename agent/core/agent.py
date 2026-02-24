"""LangChain ReAct agent with Ghostfolio tools."""

from __future__ import annotations

import logging

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from agent.config.settings import settings
from agent.core.client import GhostfolioClient
from agent.tools import ALL_TOOLS
from agent.tools.auth import set_client

logger = logging.getLogger("agentforge.agent")

SYSTEM_PROMPT = """You are a financial portfolio intelligence assistant powered by Ghostfolio.

Your capabilities:
- Analyze portfolio holdings, performance, and allocation
- Review transaction history and identify patterns
- Look up market symbols and asset information
- Assess risk exposure, diversification, and concentration
- Import new transactions when requested

Rules you MUST follow:
1. Authentication is handled automatically. You do NOT need to call the authenticate tool
   manually — it will be called behind the scenes when needed.
2. Provide data-driven answers grounded in the actual portfolio data — never guess.
3. When performing analysis, show your reasoning step by step.
4. You are NOT a financial advisor. Always include a disclaimer that your analysis is
   informational only and not investment advice.
5. If data appears incomplete or inconsistent, flag it to the user.
6. For import operations: ALWAYS call preview_import first, present the summary to the user,
   and only call import_activities with confirmed=True after they explicitly approve.
7. When asked about performance, specify the time range you used.
8. Present numbers clearly — use currency symbols, percentages, and proper formatting.
9. If a tool call fails, explain what happened and suggest alternatives.
10. Keep responses concise but thorough.
11. When asked about the PRICE of a stock or asset, ALWAYS use get_portfolio_holdings first.
    Holdings data includes the current marketPrice for every position in the portfolio.
    Only fall back to lookup_symbol if the asset is NOT in the portfolio — and note that
    lookup_symbol returns metadata only (name, exchange, asset class) but NOT the live price.
    If the user asks for a price of something not in their portfolio, explain that you can
    only provide live prices for assets currently held in the portfolio.

You have access to a live Ghostfolio instance via REST API tools.
"""


def create_agent(
    base_url: str | None = None,
    security_token: str | None = None,
):
    """Create and return a LangGraph ReAct agent with all Ghostfolio tools.

    Args:
        base_url: Override Ghostfolio URL (defaults to settings).
        security_token: Override security token (defaults to settings).

    Returns:
        A compiled LangGraph agent ready for invocation.
    """
    # Initialise the shared Ghostfolio HTTP client
    client = GhostfolioClient(
        base_url=base_url,
        security_token=security_token,
    )
    set_client(client)

    # Create the LLM (supports OpenRouter via base_url override)
    llm_kwargs: dict = {
        "model": settings.openai_model,
        "api_key": settings.openai_api_key,
        "temperature": 0,
    }
    if settings.openai_base_url:
        llm_kwargs["base_url"] = settings.openai_base_url
        logger.info(f"Using custom LLM base URL: {settings.openai_base_url}")
    llm = ChatOpenAI(**llm_kwargs)

    # If OpenRouter key is set, add it as a fallback for rate limits
    if settings.openrouter_api_key:
        openrouter_model = settings.openai_model
        # Prefix model name for OpenRouter if not already prefixed
        if "/" not in openrouter_model:
            openrouter_model = f"openai/{openrouter_model}"
        fallback_llm = ChatOpenAI(
            model=openrouter_model,
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=0,
        )
        llm = llm.with_fallbacks([fallback_llm])
        logger.info("OpenRouter fallback enabled for rate-limit resilience")

    # In-memory checkpointer — Postgres handles cross-session persistence
    checkpointer = MemorySaver()
    logger.info("Agent created with in-memory checkpointer (Postgres handles persistence)")

    # Build the ReAct agent via LangGraph
    agent = create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=SystemMessage(content=SYSTEM_PROMPT),
        checkpointer=checkpointer,
    )

    return agent
