# Tutorial: Building an AI Finance Agent with LangGraph and Ghostfolio

A comprehensive guide to building, deploying, and evaluating an AI-powered portfolio intelligence agent using LangGraph's ReAct pattern and Ghostfolio's self-hosted portfolio tracker.

## Table of Contents

1. [Introduction](#introduction)
2. [Architecture Overview](#architecture-overview)
3. [Prerequisites](#prerequisites)
4. [Step 1: Setting Up Ghostfolio](#step-1-setting-up-ghostfolio)
5. [Step 2: Building the API Client](#step-2-building-the-api-client)
6. [Step 3: Creating LangChain Tools](#step-3-creating-langchain-tools)
7. [Step 4: Wiring Up the ReAct Agent](#step-4-wiring-up-the-react-agent)
8. [Step 5: Adding Memory for Multi-Turn Conversations](#step-5-adding-memory-for-multi-turn-conversations)
9. [Step 6: Building the FastAPI Server](#step-6-building-the-fastapi-server)
10. [Step 7: Creating the Web UI](#step-7-creating-the-web-ui)
11. [Step 8: Evaluation and Testing](#step-8-evaluation-and-testing)
12. [Step 9: Deployment to Railway](#step-9-deployment-to-railway)
13. [Key Lessons Learned](#key-lessons-learned)
14. [Cost Analysis](#cost-analysis)

---

## Introduction

Financial portfolio management involves tracking holdings, analyzing performance, monitoring risk, and recording transactions. Traditional portfolio apps show data but don't let you *ask questions* about it. An AI agent bridges this gap: users ask natural language questions, and the agent decides which API calls to make, interprets the results, and responds conversationally.

**What we're building:**
- A ReAct (Reason + Act) agent that autonomously decides which tools to call
- 10 specialized tools wrapping the Ghostfolio REST API
- Multi-turn conversation memory so users can ask follow-up questions
- Auto-authentication so the agent handles JWT tokens transparently
- A web UI and REST API for interaction
- An evaluation framework with 70 test queries

**Tech stack:**
- **LLM**: GPT-4o (via OpenAI API)
- **Agent framework**: LangGraph with ReAct pattern
- **Portfolio backend**: Ghostfolio (self-hosted via Docker)
- **Web framework**: FastAPI
- **Deployment**: Railway (4 services)

---

## Architecture Overview

```
User Query
    |
    v
FastAPI Server (/query)
    |
    v
LangGraph ReAct Agent (GPT-4o)
    |
    +--> Selects tool(s) based on query
    |
    v
LangChain Tools (10 tools)
    |
    v
GhostfolioClient (httpx, auto-auth, retry)
    |
    v
Ghostfolio REST API
    |
    v
PostgreSQL + Redis
```

The agent uses the ReAct pattern: it **reasons** about which tool to call, **acts** by calling it, **observes** the result, and repeats until it has enough information to respond. LangGraph's `create_react_agent` handles this loop automatically.

---

## Prerequisites

- Python 3.11+
- Docker and Docker Compose
- OpenAI API key (GPT-4o access)
- Basic familiarity with FastAPI and async Python

---

## Step 1: Setting Up Ghostfolio

Ghostfolio is a self-hosted portfolio tracker with a REST API. We use the official Docker image — no forking or modification needed.

**Docker Compose setup:**

```yaml
services:
  ghostfolio:
    image: ghostfolio/ghostfolio:latest
    environment:
      DATABASE_URL: postgresql://ghostfolio:password@postgres:5432/ghostfolio
      REDIS_HOST: redis
      ACCESS_TOKEN_SALT: your-random-salt
      JWT_SECRET_KEY: your-random-jwt-secret
      POSTGRES_PASSWORD: password
    ports:
      - "3333:3333"
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ghostfolio
      POSTGRES_USER: ghostfolio
      POSTGRES_PASSWORD: password

  redis:
    image: redis:7-alpine
```

After starting with `docker compose up`, visit `http://localhost:3333` and create your account. Generate a **Security Token** from the user settings — this is the key your agent uses to authenticate.

---

## Step 2: Building the API Client

The API client wraps Ghostfolio's REST API with auto-authentication and retry logic.

**Key design decisions:**

1. **Auto-authentication**: The client automatically obtains a JWT token before the first API call, so the LLM never needs to call an "authenticate" tool manually. This saves one round-trip per conversation.

2. **401 re-authentication**: If a token expires mid-session, the client catches the 401, re-authenticates, and retries — transparent to the agent.

3. **Retry with backoff**: Network failures trigger up to 3 retries with exponential backoff (1s to 10s). This prevents demo failures from transient issues.

```python
# Simplified pattern for the centralized request method
async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
    await self._ensure_authenticated()
    headers = self._build_headers()

    for attempt in range(3):
        try:
            response = await self.client.request(method, url, headers=headers, **kwargs)
            if response.status_code == 401:
                await self.authenticate()
                headers = self._build_headers()
                continue
            return response
        except (httpx.ConnectError, httpx.ReadTimeout):
            if attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)
```

---

## Step 3: Creating LangChain Tools

Each tool is a `@tool`-decorated async function that the agent can call. LangChain uses the function's docstring and type hints to tell the LLM what the tool does and what parameters it expects.

**Example: Portfolio holdings tool**

```python
from langchain_core.tools import tool

@tool
async def get_portfolio_holdings() -> str:
    """Get current portfolio holdings including positions, values, and quantities."""
    client = get_client()
    data = await client.get_holdings()
    return json.dumps(data, indent=2)
```

**Tool design principles:**

- **Return JSON strings** — the LLM can parse structured data better than custom formats
- **Use descriptive docstrings** — this is what GPT-4o reads to decide which tool to call
- **Keep tools focused** — one tool per API concept (don't combine holdings + performance)
- **Add parameter descriptions** — for tools that take inputs, type hints guide the LLM

**The 10 tools we built:**

| Tool | Purpose | Parameters |
|------|---------|------------|
| `authenticate` | Get JWT token (auto-called) | None |
| `health_check` | Verify API connectivity | None |
| `get_portfolio_holdings` | Current positions | None |
| `get_portfolio_performance` | Returns over time range | `range` (1d, 1w, 1m, 3m, ytd, 1y, 5y, max) |
| `get_portfolio_details` | Allocation, sectors, breakdown | None |
| `get_orders` | Transaction history | None |
| `preview_import` | Preview a transaction (safety) | `activities` (JSON) |
| `import_activities` | Execute confirmed import | `activities`, `confirmed` |
| `get_accounts` | List investment accounts | None |
| `lookup_symbol` | Search ticker symbols | `query` |
| `get_user_settings` | User preferences | None |

---

## Step 4: Wiring Up the ReAct Agent

LangGraph's `create_react_agent` creates a complete ReAct loop with just a few lines:

```python
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o", temperature=0)

agent = create_react_agent(
    model=llm,
    tools=ALL_TOOLS,
    prompt=SYSTEM_PROMPT,
)
```

**The system prompt is critical.** It tells the agent:
- What it is (a financial portfolio assistant)
- What data sources it has access to
- Rules for behavior (e.g., always preview before importing)
- How to handle multi-turn conversations

---

## Step 5: Adding Memory for Multi-Turn Conversations

Without memory, each query starts fresh — the agent can't answer "Which one performed best?" after "Show me my holdings." LangGraph's `MemorySaver` checkpointer solves this:

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
agent = create_react_agent(
    model=llm,
    tools=ALL_TOOLS,
    prompt=SYSTEM_PROMPT,
    checkpointer=checkpointer,
)
```

Each conversation uses a `thread_id` to maintain its own history:

```python
result = await agent.ainvoke(
    {"messages": [{"role": "user", "content": user_query}]},
    config={"configurable": {"thread_id": "user-session-123"}},
)
```

The checkpointer stores the full message history, so the agent has context from previous turns.

---

## Step 6: Building the FastAPI Server

The server exposes the agent as a REST API:

```python
@app.post("/query")
async def query_agent(request: QueryRequest):
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": request.message}]},
        config={"configurable": {"thread_id": request.thread_id or "default"}},
    )
    response_text = result["messages"][-1].content
    return {"response": response_text, "thread_id": request.thread_id}
```

**Key additions:**
- Health endpoint that checks both the agent and Ghostfolio connectivity
- CORS middleware for the web UI
- Static file serving for the frontend
- Request logging with timing

---

## Step 7: Creating the Web UI

A single-page chat interface served as a static HTML file. Key features:

- Dark theme matching financial app aesthetics
- Suggestion chips for common queries (persistent across messages)
- Thread-based conversations (random ID per session)
- Health indicator showing Ghostfolio connectivity
- Auto-resizing textarea input

The UI communicates with the FastAPI `/query` endpoint via `fetch()`.

---

## Step 8: Evaluation and Testing

We built a 70-query eval dataset covering 11 categories. The eval runner:

1. Loads each query from `data/eval_datasets/sample_queries.json`
2. Sends it through the agent
3. Checks if the expected tools were called (subset match)
4. Checks if the response contains expected keywords
5. Reports pass/fail with an overall score

```bash
python tests/eval/run_eval.py
```

**Difficulty breakdown:**
- **Easy** (35 queries): Direct tool mapping, single tool call
- **Medium** (24 queries): Requires parameter extraction, filtering, or aggregation
- **Hard** (11 queries): Multi-tool orchestration, financial reasoning, edge cases

---

## Step 9: Deployment to Railway

Railway hosts all 4 services:

| Service | Image/Source | Port |
|---------|-------------|------|
| Agent (FastAPI) | GitHub repo | 8000 |
| Ghostfolio | `ghostfolio/ghostfolio:latest` | 3333 |
| PostgreSQL | `postgres:15` | 5432 |
| Redis | `redis:7-alpine` | 6379 |

**Environment variables needed:**
- `OPENAI_API_KEY` — for GPT-4o
- `GHOSTFOLIO_URL` — internal Railway URL for Ghostfolio
- `GHOSTFOLIO_SECURITY_TOKEN` — from Ghostfolio user settings
- `DATABASE_URL`, `REDIS_HOST`, etc. for Ghostfolio

Railway auto-deploys on git push to main.

---

## Key Lessons Learned

### 1. Auto-auth saves LLM round-trips
Making authentication automatic (instead of a tool the LLM must call) eliminates one round-trip per conversation. The LLM occasionally forgot to call it first, causing crashes.

### 2. Faster models for tool-heavy tasks
For agents that make many tool calls, model speed matters more than peak intelligence. GPT-4o provides a good balance of capability and latency.

### 3. Batch operations for performance
When the agent generates multiple actions (e.g., creating 6 board objects), batching them into a single database write is dramatically faster than sequential writes.

### 4. Human-in-the-loop for destructive operations
The `preview_import` → `import_activities` two-step pattern prevents accidental data modification. The agent shows what it will do before doing it.

### 5. Eval datasets catch regressions
After changing the system prompt or tool descriptions, running the eval suite immediately shows if any queries broke. The 70-query dataset covers enough edge cases to catch most regressions.

---

## Cost Analysis

**Per-query costs (GPT-4o):**

| Query Type | Avg Tokens | Estimated Cost |
|------------|-----------|----------------|
| Simple (1 tool) | ~2,000 | ~$0.015 |
| Medium (1-2 tools) | ~3,500 | ~$0.025 |
| Complex (3+ tools) | ~5,000 | ~$0.035 |

**Monthly projections:**

| Usage Tier | Queries/Month | Monthly Cost |
|------------|---------------|-------------|
| Personal | 100 | ~$2 |
| Active User | 500 | ~$10 |
| Power User | 2,000 | ~$40 |

Infrastructure costs (Railway): ~$5-10/month for all 4 services on the hobby plan.

---

## Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Ghostfolio API](https://ghostfolio.dev)
- [AgentForge Source Code](https://github.com/s85191939/AgentForge)
- [Eval Dataset](https://github.com/s85191939/AgentForge/tree/main/data/eval_datasets)
