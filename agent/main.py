"""FastAPI application — serves the AgentForge Finance agent over HTTP."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import pathlib

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent.config.settings import settings
from agent.core.agent import create_agent
from agent.tools.auth import get_client

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("agentforge")


# ---------------------------------------------------------------------------
# Lifespan — initialise / teardown the Ghostfolio client
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start-up: create agent. Shutdown: close HTTP client."""
    logger.info("Starting AgentForge Finance agent...")
    app.state.agent = create_agent()
    logger.info("Agent ready.")
    yield
    try:
        client = get_client()
        await client.close()
        logger.info("HTTP client closed.")
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
# Static files — serve the chat web UI
# ---------------------------------------------------------------------------

STATIC_DIR = pathlib.Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Middleware — request logging with timing
# ---------------------------------------------------------------------------

@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.time()
    logger.info(f"[{request_id}] {request.method} {request.url.path}")
    response = await call_next(request)
    elapsed = time.time() - start
    logger.info(f"[{request_id}] completed in {elapsed:.2f}s status={response.status_code}")
    response.headers["X-Request-ID"] = request_id
    return response


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    """User query to the agent."""
    message: str = Field(..., min_length=1, max_length=2000)
    thread_id: str = Field(default="default", min_length=1, max_length=100)


class QueryResponse(BaseModel):
    """Agent response."""
    response: str
    thread_id: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    """Serve the chat web UI."""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
async def health():
    """Health check for the agent server and Ghostfolio connectivity."""
    gf_status = "unknown"
    try:
        client = get_client()
        result = await client.health_check()
        gf_status = result.get("status", "unknown")
    except Exception:
        gf_status = "unreachable"
    return {
        "status": "ok",
        "service": "agentforge-finance",
        "ghostfolio": gf_status,
    }


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """Send a natural language query to the finance agent."""
    agent = app.state.agent

    try:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": req.message}]},
            config={
                "configurable": {"thread_id": req.thread_id},
                "recursion_limit": settings.agent_max_iterations * 2,
            },
        )

        # Extract the final assistant message
        messages = result.get("messages", [])
        if messages:
            final = messages[-1]
            content = final.content if hasattr(final, "content") else str(final)
        else:
            content = "No response generated."

        return QueryResponse(response=content, thread_id=req.thread_id)

    except httpx.ConnectError:
        logger.error("Cannot reach Ghostfolio instance")
        raise HTTPException(
            status_code=502,
            detail="Cannot reach Ghostfolio instance. Is it running?",
        )
    except RecursionError:
        logger.error("Agent exceeded max iterations")
        raise HTTPException(
            status_code=500,
            detail="Agent exceeded maximum iterations. Try a simpler query.",
        )
    except Exception as e:
        logger.exception(f"Unhandled error: {e}")
        raise HTTPException(status_code=500, detail="Internal error processing query.")


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
