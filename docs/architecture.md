# Agent Architecture Document

## 1. System Overview

AgentForge Finance is an AI-powered portfolio intelligence agent that wraps the open-source [Ghostfolio](https://github.com/ghostfolio/ghostfolio) wealth management platform. The agent accepts natural language queries and translates them into structured API calls, returning synthesized, human-readable financial insights.

### Design Decision: Separate Service Architecture

The agent runs as an **independent Python service** that communicates with Ghostfolio via its REST API, rather than being embedded into Ghostfolio's NestJS codebase. This was chosen for three reasons:

1. **License isolation** -- Ghostfolio is AGPL-3.0 licensed. A separate service communicating over HTTP has no copyleft obligation.
2. **Ecosystem leverage** -- Python provides superior AI/ML tooling (LangChain, LangGraph, OpenAI SDK) compared to the NestJS ecosystem.
3. **Independent deployment** -- The agent can be versioned, scaled, and deployed independently of the Ghostfolio instance.

## 2. Architecture Diagram

```
                    +------------------+
                    |   User Clients   |
                    | (Web UI / CLI /  |
                    |     cURL)        |
                    +--------+---------+
                             |
                     HTTP POST /query
                             |
                    +--------v---------+
                    |   FastAPI Server  |
                    |  (agent/main.py)  |
                    |                   |
                    | - Request logging |
                    | - Input validation|
                    | - Error handling  |
                    +--------+---------+
                             |
                    +--------v---------+
                    | LangGraph ReAct  |
                    |     Agent         |
                    | (agent/core/      |
                    |  agent.py)        |
                    |                   |
                    | - GPT-4o LLM     |
                    | - MemorySaver    |
                    | - System prompt  |
                    | - 11 tools       |
                    +--------+---------+
                             |
                    +--------v---------+
                    | GhostfolioClient |
                    | (agent/core/      |
                    |  client.py)       |
                    |                   |
                    | - Auto-auth      |
                    | - Retry (3x)     |
                    | - 401 re-auth    |
                    +--------+---------+
                             |
                     REST API (HTTP)
                             |
                    +--------v---------+
                    |    Ghostfolio    |
                    | (NestJS backend) |
                    +--------+---------+
                             |
              +--------------+--------------+
              |                             |
     +--------v--------+          +--------v--------+
     |   PostgreSQL 15  |          |    Redis 7      |
     |  (Persistent     |          |  (Sessions,     |
     |   storage)       |          |   caching)      |
     +-----------------+          +-----------------+
```

## 3. Core Components

### 3.1 LangGraph ReAct Agent (`agent/core/agent.py`)

The agent uses LangGraph's `create_react_agent()` which implements the **ReAct (Reasoning + Acting)** pattern:

1. **Reason** -- The LLM analyzes the user query and decides which tool to call
2. **Act** -- The tool executes against the Ghostfolio API
3. **Observe** -- The LLM reads the tool result
4. **Repeat** -- Steps 1-3 loop until the LLM has enough information to respond

Configuration:
- **LLM**: OpenAI GPT-4o with `temperature=0` for deterministic outputs
- **Checkpointer**: `MemorySaver` provides per-thread conversation memory
- **Recursion limit**: `agent_max_iterations * 2` (default: 20 steps) prevents infinite loops

### 3.2 Ghostfolio HTTP Client (`agent/core/client.py`)

A centralized async HTTP client using `httpx` with three reliability layers:

- **Auto-authentication**: On first API call, the client exchanges the security token for a JWT. No manual auth step required.
- **Retry with backoff**: All requests use `tenacity` -- 3 attempts with exponential backoff (1s to 10s) for `ConnectError` and `ReadTimeout`.
- **401 re-authentication**: If a request returns 401, the client clears the JWT, re-authenticates, and retries the request once.

### 3.3 Tool Layer (`agent/tools/`)

11 LangChain `@tool`-decorated functions organized by domain:

| Module | Tools | Purpose |
|---|---|---|
| `auth.py` | `authenticate`, `health_check` | Connection management |
| `portfolio.py` | `get_portfolio_holdings`, `get_portfolio_performance`, `get_portfolio_details` | Portfolio analysis |
| `orders.py` | `get_orders`, `preview_import`, `import_activities` | Transaction management |
| `accounts.py` | `get_accounts` | Account information |
| `symbols.py` | `lookup_symbol` | Market data lookup |
| `user.py` | `get_user_settings` | User configuration |

### 3.4 Human-in-the-Loop Safety

Write operations (importing activities) use a two-phase confirmation pattern:

1. `preview_import` -- Validates the activity JSON structure (required fields: `currency`, `dataSource`, `date`, `fee`, `quantity`, `symbol`, `type`, `unitPrice`) and returns a formatted preview.
2. `import_activities` -- Requires an explicit `confirmed=True` parameter. Rejects execution without confirmation.

The system prompt instructs the LLM to always call `preview_import` first and wait for user approval before calling `import_activities`.

### 3.5 FastAPI Server (`agent/main.py`)

The HTTP server provides:

- `GET /` -- Serves the chat web UI (single-page HTML)
- `GET /health` -- Health check (verifies Ghostfolio connectivity)
- `POST /query` -- Accepts `{message, thread_id}`, returns `{response, thread_id}`
- Request logging middleware with timing and request IDs
- Specific error handling: 502 for Ghostfolio unreachable, 500 for recursion limit

### 3.6 Configuration (`agent/config/settings.py`)

Pydantic `BaseSettings` with field validators that fail fast on missing API keys. An `AGENTFORGE_TESTING=1` environment variable bypass allows unit tests to run without real credentials.

## 4. Data Flow Example

**User asks**: "What are my holdings?"

1. FastAPI receives `POST /query` with `{message: "What are my holdings?", thread_id: "abc"}`
2. LangGraph agent invokes with `MemorySaver` config for thread `"abc"`
3. GPT-4o reasons: "I need portfolio holdings" and emits a `get_portfolio_holdings` tool call
4. The tool calls `GhostfolioClient.get_portfolio_holdings()`
5. Client auto-authenticates (if needed), sends `GET /api/v1/portfolio/holdings`
6. Ghostfolio queries PostgreSQL, returns JSON with holdings data
7. Tool returns structured result to the LLM
8. GPT-4o synthesizes the data into a formatted markdown response
9. FastAPI returns `{response: "Here are your holdings...", thread_id: "abc"}`

## 5. Deployment Architecture (Railway)

Four services deployed on Railway:

| Service | Image/Source | Purpose |
|---|---|---|
| Agent (lovely-vitality) | Python 3.11 + Dockerfile | FastAPI + LangGraph agent |
| Ghostfolio | `ghostfolio/ghostfolio:latest` | Wealth management backend |
| PostgreSQL 15 | Railway managed | Persistent data storage |
| Redis 7 | Railway managed | Session/cache store |

All services communicate over Railway's internal network. The agent service is the only public-facing endpoint.
