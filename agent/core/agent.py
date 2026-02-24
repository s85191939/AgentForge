"""LangChain ReAct agent with Ghostfolio tools."""

from __future__ import annotations

import logging
import pathlib

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

You have access to a live Ghostfolio instance via REST API tools.
"""


def _get_db_path() -> str:
    """Return the path for the SQLite checkpoint database."""
    # Use /data if it exists (Railway persistent volume), else local .data dir
    data_dir = pathlib.Path("/data")
    if not data_dir.exists():
        data_dir = pathlib.Path(__file__).resolve().parent.parent.parent / ".data"
        data_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(data_dir / "memory.db")
    logger.info(f"Checkpoint DB: {db_path}")
    return db_path


async def create_agent(
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

    # Create the LLM
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )

    # Persistent SQLite checkpointer for cross-session memory
    # Falls back to in-memory if SQLite setup fails (e.g. missing deps in container)
    checkpointer: object
    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        db_path = _get_db_path()
        checkpointer = AsyncSqliteSaver.from_conn_string(db_path)
        await checkpointer.setup()
        logger.info("Using persistent SQLite memory")
    except Exception as exc:
        logger.warning(f"SQLite checkpointer failed ({exc}), falling back to in-memory")
        checkpointer = MemorySaver()

    # Build the ReAct agent via LangGraph
    agent = create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=SystemMessage(content=SYSTEM_PROMPT),
        checkpointer=checkpointer,
    )

    return agent
