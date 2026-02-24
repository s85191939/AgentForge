"""FastAPI application — serves the AgentForge Finance agent over HTTP."""

from __future__ import annotations

import logging
import pathlib
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import ToolMessage
from pydantic import BaseModel, Field

from agent.config.settings import settings
from agent.core.agent import create_agent
from agent.core.formatter import format_response
from agent.core.verification import verify_response
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
    app.state.agent = await create_agent()
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


class ToolCallInfo(BaseModel):
    """Info about a tool call made during agent reasoning."""
    tool: str
    result_preview: str = ""


class VerificationInfo(BaseModel):
    """Verification check results."""
    passed: bool = True
    warnings: list[str] = []


class QueryResponse(BaseModel):
    """Agent response with debug info."""
    response: str
    thread_id: str
    tools_called: list[ToolCallInfo] = []
    verification: VerificationInfo = VerificationInfo()
    citations: list[str] = []
    confidence: str = "medium"


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


@app.get("/api/portfolio-summary")
async def portfolio_summary():
    """Return raw portfolio data for the dashboard sidebar and ticker."""
    try:
        client = get_client()
        holdings = await client.get_portfolio_holdings()
        performance = await client.get_portfolio_performance(range_="1d")
        return {
            "holdings": holdings.get("holdings", []),
            "performance": performance,
        }
    except Exception as e:
        logger.warning(f"Portfolio summary error: {e}")
        return {"holdings": [], "performance": {}, "error": str(e)}


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

        # Extract the final assistant message and tool call info
        messages = result.get("messages", [])

        # Collect tool calls and results for debug panel
        tools_called: list[ToolCallInfo] = []
        tool_results: list[str] = []
        for m in messages:
            if isinstance(m, ToolMessage):
                preview = (m.content or "")[:200]
                tools_called.append(ToolCallInfo(
                    tool=m.name or "unknown",
                    result_preview=preview,
                ))
                tool_results.append(m.content or "")
            if hasattr(m, "tool_calls"):
                for tc in m.tool_calls:
                    name = tc.get("name", "unknown")
                    # Avoid duplicates — tool_calls appear before ToolMessage
                    if not any(t.tool == name for t in tools_called):
                        tools_called.append(ToolCallInfo(tool=name))

        if messages:
            final = messages[-1]
            content = final.content if hasattr(final, "content") else str(final)
        else:
            content = "No response generated."

        # Run domain-specific verification checks
        vr = verify_response(content, tool_results or None)
        content = vr.cleaned_response  # May have disclaimer appended

        # Format response with citations and confidence
        tool_names = [tc.tool for tc in tools_called]
        formatted = format_response(content, tool_names, tool_results or None)

        return QueryResponse(
            response=content,
            thread_id=req.thread_id,
            tools_called=tools_called,
            verification=VerificationInfo(
                passed=vr.passed,
                warnings=vr.warnings,
            ),
            citations=formatted.citations,
            confidence=formatted.confidence,
        )

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
