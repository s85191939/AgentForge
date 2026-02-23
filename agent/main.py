"""FastAPI application — serves the AgentForge Finance agent over HTTP."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agent.config.settings import settings
from agent.core.agent import create_agent
from agent.core.client import GhostfolioClient
from agent.tools.auth import get_client


# ---------------------------------------------------------------------------
# Lifespan — initialise / teardown the Ghostfolio client
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start-up: create agent. Shutdown: close HTTP client."""
    app.state.agent = create_agent()
    yield
    try:
        client = get_client()
        await client.close()
    except RuntimeError:
        pass


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AgentForge Finance",
    description="AI-powered financial portfolio intelligence agent for Ghostfolio",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    """User query to the agent."""
    message: str
    thread_id: str = "default"


class QueryResponse(BaseModel):
    """Agent response."""
    response: str
    thread_id: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Health check for the agent server."""
    return {"status": "ok", "service": "agentforge-finance"}


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """Send a natural language query to the finance agent."""
    agent = app.state.agent

    try:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": req.message}]},
            config={"configurable": {"thread_id": req.thread_id}},
        )

        # Extract the final assistant message
        messages = result.get("messages", [])
        if messages:
            final = messages[-1]
            content = final.content if hasattr(final, "content") else str(final)
        else:
            content = "No response generated."

        return QueryResponse(response=content, thread_id=req.thread_id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "agent.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
