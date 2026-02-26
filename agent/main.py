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
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import ToolMessage
from openai import (
    APIConnectionError as OpenAIConnectionError,
)
from openai import (
    APITimeoutError as OpenAITimeoutError,
)
from openai import (
    RateLimitError as OpenAIRateLimitError,
)
from pydantic import BaseModel, Field

from agent.config.settings import settings
from agent.core.agent import create_agent
from agent.core.cache import ResponseCache
from agent.core.database import (
    close_db,
    create_thread,
    delete_thread,
    init_db,
    is_available,
    list_threads,
    load_messages,
    rename_thread,
    save_message,
)
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
# Response cache — avoids redundant LLM calls for repeated identical queries
# TTL = 5 minutes, max 128 entries
# ---------------------------------------------------------------------------

_response_cache = ResponseCache(ttl_seconds=300, max_size=128)


# ---------------------------------------------------------------------------
# Lifespan — initialise / teardown the Ghostfolio client + database
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start-up: create agent, init database. Shutdown: close connections."""
    logger.info("Starting AgentForge Finance agent...")
    await init_db(settings.database_url or None)
    app.state.agent = create_agent()
    logger.info("Agent ready.")
    yield
    await close_db()
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
# Public Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    """Serve the chat web UI."""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
async def health():
    """Health check for the agent server, Ghostfolio, and database."""
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
        "database": "connected" if is_available() else "unavailable",
    }


# ---------------------------------------------------------------------------
# Thread Management API
# ---------------------------------------------------------------------------

@app.get("/api/threads")
async def get_threads():
    """List all chat threads, most recently updated first."""
    threads = await list_threads()
    return {"threads": threads}


class CreateThreadRequest(BaseModel):
    """Optional title when creating a thread."""
    title: str = "New Chat"


@app.post("/api/threads")
async def new_thread(req: CreateThreadRequest | None = None):
    """Create a new chat thread."""
    title = (req.title.strip() if req and req.title else "New Chat") or "New Chat"
    thread = await create_thread(title=title)
    if thread is None:
        # DB unavailable — return a local-only thread ID
        return {
            "id": str(uuid.uuid4()),
            "title": title,
            "created_at": "",
            "updated_at": "",
        }
    return thread


@app.get("/api/threads/{thread_id}/messages")
async def get_messages(thread_id: str):
    """Load all messages for a thread."""
    messages = await load_messages(thread_id)
    return {"messages": messages}


class RenameRequest(BaseModel):
    """Rename a chat thread."""
    title: str = Field(..., min_length=1, max_length=100)


@app.patch("/api/threads/{thread_id}")
async def update_thread(thread_id: str, req: RenameRequest):
    """Rename a chat thread."""
    ok = await rename_thread(thread_id, req.title.strip())
    if not ok:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"id": thread_id, "title": req.title.strip()}


@app.delete("/api/threads/{thread_id}")
async def remove_thread(thread_id: str):
    """Delete a thread and all its messages."""
    await delete_thread(thread_id)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Portfolio Summary
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Agent Query
# ---------------------------------------------------------------------------

@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """Send a natural language query to the finance agent."""
    agent = app.state.agent
    langgraph_thread_id = req.thread_id

    # --- Cache check: return cached response for repeated identical queries ---
    cached = _response_cache.get(req.message, req.thread_id)
    if cached is not None:
        return QueryResponse(**cached)

    try:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": req.message}]},
            config={
                "configurable": {"thread_id": langgraph_thread_id},
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

        # Persist messages to Postgres (if available)
        if is_available():
            await save_message(req.thread_id, "user", req.message)
            await save_message(
                req.thread_id,
                "agent",
                content,
                metadata={
                    "tools_called": [tc.model_dump() for tc in tools_called],
                    "verification": {"passed": vr.passed, "warnings": vr.warnings},
                    "citations": formatted.citations,
                    "confidence": formatted.confidence,
                },
            )

        response_data = {
            "response": content,
            "thread_id": req.thread_id,
            "tools_called": [tc.model_dump() for tc in tools_called],
            "verification": {"passed": vr.passed, "warnings": vr.warnings},
            "citations": formatted.citations,
            "confidence": formatted.confidence,
        }

        # Cache the successful response
        _response_cache.put(req.message, req.thread_id, response_data)

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

    # --- Graceful LLM fallback: friendly errors when AI services are down ---
    except (OpenAIConnectionError, OpenAITimeoutError):
        logger.error("LLM service unreachable (both primary and fallback)")
        return QueryResponse(
            response=(
                "I'm temporarily unable to process your request because the AI "
                "service is unreachable. Please try again in a few moments."
            ),
            thread_id=req.thread_id,
            tools_called=[],
            verification=VerificationInfo(),
            citations=[],
            confidence="low",
        )
    except OpenAIRateLimitError:
        logger.error("LLM rate-limited on all providers (OpenAI + OpenRouter)")
        return QueryResponse(
            response=(
                "The AI service is currently experiencing high demand and both "
                "providers are rate-limited. Please wait a moment and try again."
            ),
            thread_id=req.thread_id,
            tools_called=[],
            verification=VerificationInfo(),
            citations=[],
            confidence="low",
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
        # Detect LLM errors wrapped by LangChain/LangGraph
        err_str = str(e).lower()
        llm_error_signals = [
            "rate limit", "rate_limit", "429",
            "connection error", "timeout", "timed out",
            "openai", "openrouter", "api_connection",
        ]
        if any(signal in err_str for signal in llm_error_signals):
            logger.error("LLM service error (wrapped): %s", e)
            return QueryResponse(
                response=(
                    "The AI service encountered an error. This may be a temporary "
                    "issue — please try again in a few moments."
                ),
                thread_id=req.thread_id,
                tools_called=[],
                verification=VerificationInfo(),
                citations=[],
                confidence="low",
            )
        logger.exception("Unhandled error: %s", e)
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
