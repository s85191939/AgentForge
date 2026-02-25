# AgentForge Finance

AI-powered financial portfolio intelligence agent for [Ghostfolio](https://github.com/ghostfolio/ghostfolio).

## Live Demo

**Web UI:** [https://lovely-vitality-production-fdc1.up.railway.app](https://lovely-vitality-production-fdc1.up.railway.app)

## Overview

AgentForge Finance is a LangChain/LangGraph-based AI agent that connects to a Ghostfolio instance and answers natural language questions about your investment portfolio. It supports multi-turn conversations, auto-authentication, retry with exponential backoff, and human-in-the-loop confirmation for write operations.

### What can it do?

- View portfolio holdings, performance, and allocation breakdowns
- Look up stock/ETF symbols and their details
- List transaction history (buys, sells, dividends)
- Import new activities with preview + confirmation safety
- View account details and user settings
- Multi-turn memory (remembers context within a conversation)
- Renamable chat threads with auto-deduplication
- Live portfolio ticker bar with real-time prices

## Architecture

```
User (Browser / CLI)
        |
        v
  FastAPI Server (Python 3.11)
        |
        v
  LangGraph ReAct Agent (GPT-4o)
    |                    |
    v                    v
  OpenAI API         OpenRouter API
  (primary)          (fallback on 429)
        |
        v
  Ghostfolio REST API (NestJS + Angular)
    |            |           |
    v            v           v
  PostgreSQL   Redis    Market Data
  (Prisma)    (cache)   (providers)
```

The agent runs as a **separate service** that communicates with Ghostfolio via its REST API. This architecture avoids AGPL-3.0 license obligations and leverages Python's AI/ML ecosystem.

## Tech Stack

### Agent Layer (Python)

| Component | Technology | Purpose |
|---|---|---|
| **Agent Framework** | [LangChain](https://python.langchain.com/) + [LangGraph](https://langchain-ai.github.io/langgraph/) | ReAct agent pattern with autonomous reason-act-observe loop |
| **LLM** | OpenAI GPT-4o | Primary language model for tool selection and response generation |
| **LLM Fallback** | [OpenRouter](https://openrouter.ai/) | Automatic fallback via `with_fallbacks()` on 429 rate limits |
| **API Server** | [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) | Async HTTP server with middleware, CORS, health checks |
| **HTTP Client** | [httpx](https://www.python-httpx.org/) (async) + [tenacity](https://github.com/jd/tenacity) (retry) | Auto-auth, exponential backoff, 401 re-auth |
| **Config** | [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) | Type-safe env var loading with field validators |
| **Chat Persistence** | [asyncpg](https://github.com/MagicStack/asyncpg) + PostgreSQL | Multi-thread chat history with full message metadata |
| **Agent Memory** | LangGraph `MemorySaver` | Per-thread conversation context for multi-turn reasoning |

### Observability

| Tool | Purpose |
|---|---|
| [LangSmith](https://smith.langchain.com/) | Tracing every agent call — tool selection, LLM reasoning, latency, token usage. Native LangChain integration via `LANGCHAIN_TRACING_V2=true`. |
| Tool Call Debug Panel | In-app collapsible panel showing tools called, result previews, verification status, and confidence for every response. |

### Target Application (Ghostfolio Fork)

| Component | Technology | Purpose |
|---|---|---|
| **Backend** | [NestJS](https://nestjs.com/) (TypeScript) | REST API for portfolio data, orders, accounts |
| **Frontend** | [Angular](https://angular.io/) | Wealth management web UI |
| **ORM** | [Prisma](https://www.prisma.io/) | Database access layer |
| **Database** | PostgreSQL | Persistent storage for users, orders, market data |
| **Cache** | Redis | Session store and data caching |
| **Monorepo** | [Nx](https://nx.dev/) | Build system for the NestJS + Angular workspace |

### Infrastructure

| Component | Technology |
|---|---|
| **Deployment** | [Railway](https://railway.app) (4 services: Agent, Ghostfolio, PostgreSQL, Redis) |
| **Containerization** | Docker (Dockerfile for agent, Docker Compose for local dev) |
| **CI/Testing** | pytest + pytest-asyncio + respx (19 unit tests) |

### Why LangChain + LangGraph?

We chose LangChain/LangGraph over alternatives (CrewAI, AutoGen, Semantic Kernel) because:

1. **Native tool integration** — LangChain's `@tool` decorator maps directly to Ghostfolio API endpoints with type-safe schemas
2. **ReAct agent pattern** — LangGraph's `create_react_agent` handles the reason-act-observe loop with built-in tool calling
3. **Fallback chains** — `with_fallbacks()` lets us chain OpenAI and OpenRouter for rate limit resilience
4. **Observability** — LangSmith tracing is zero-config (just set env vars)
5. **Ecosystem** — largest community, best docs, most examples for financial AI agents

## Quick Start

### Option 1: Use the deployed version

Visit the [live web UI](https://lovely-vitality-production-fdc1.up.railway.app) — no setup required.

### Option 2: Run locally

```bash
# 1. Clone the repo
git clone https://github.com/s85191939/AgentForge.git
cd AgentForge

# 2. Start Ghostfolio + PostgreSQL + Redis via Docker
cp .env.example .env   # Then edit with your values (see Configuration below)
docker compose -f docker/docker-compose.yml up -d

# 3. Create a Python 3.11 virtual environment
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 4. Seed demo portfolio data (optional)
python scripts/seed_data.py

# 5a. Run the Web UI + API server
python -m agent.main
# Open http://localhost:8000 in your browser

# 5b. Or run the interactive CLI
python -m agent.cli
```

## Configuration

Copy `.env.example` to `.env` and fill in the values:

| Variable | Required | Description |
|---|---|---|
| `GHOSTFOLIO_BASE_URL` | Yes | URL of your Ghostfolio instance (default: `http://localhost:3333`) |
| `GHOSTFOLIO_SECURITY_TOKEN` | Yes | Security token from Ghostfolio settings |
| `OPENAI_API_KEY` | Yes | OpenAI API key for GPT-4o |
| `OPENAI_MODEL` | No | LLM model to use (default: `gpt-4o`) |
| `OPENROUTER_API_KEY` | No | OpenRouter API key for rate-limit fallback |
| `LANGCHAIN_TRACING_V2` | No | Enable LangSmith tracing (default: `true`) |
| `LANGCHAIN_API_KEY` | No | LangSmith API key for observability |
| `LANGCHAIN_PROJECT` | No | LangSmith project name (default: `agentforge-finance`) |

## Usage

### Web UI

Navigate to `http://localhost:8000` (local) or the [live URL](https://lovely-vitality-production-fdc1.up.railway.app). The chat interface includes:

- Suggestion buttons for common queries
- Health status indicator (green = Ghostfolio connected)
- Multi-turn conversation memory per thread
- Renamable chat threads (click title to edit)
- Collapsible tool call debug panel on every response
- Live portfolio ticker bar with real-time prices
- Markdown-formatted responses with syntax highlighting

### CLI

```bash
source .venv/bin/activate
python -m agent.cli
```

### API (cURL)

```bash
# Health check
curl https://lovely-vitality-production-fdc1.up.railway.app/health

# Query the agent
curl -X POST https://lovely-vitality-production-fdc1.up.railway.app/query \
  -H 'Content-Type: application/json' \
  -d '{"message": "What are my holdings?", "thread_id": "my-session"}'
```

## Agent Tools

| Tool | Description | Read/Write |
|---|---|---|
| `authenticate` | Authenticate with Ghostfolio (auto-called) | Read |
| `health_check` | Check Ghostfolio connectivity | Read |
| `get_portfolio_holdings` | List all portfolio holdings with live prices | Read |
| `get_portfolio_performance` | Get portfolio performance metrics | Read |
| `get_portfolio_details` | Get detailed portfolio breakdown | Read |
| `get_orders` | List transaction history | Read |
| `preview_import` | Preview activities before importing | Read |
| `import_activities` | Import activities (requires `confirmed=True`) | Write |
| `get_accounts` | List investment accounts | Read |
| `lookup_symbol` | Search for stock/ETF symbols | Read |
| `get_user_settings` | Get user preferences | Read |

## Key Features

### Tool Call Debug Panel
Every agent response includes a collapsible debug panel showing which tools were called, a preview of each tool's raw output, verification status (VERIFIED/WARNING), and a confidence badge (HIGH/MEDIUM/LOW). Click the "N tools called" bar below any response to expand.

### Auto-Authentication
The HTTP client automatically authenticates on the first API call and re-authenticates on 401 responses. No manual auth step needed.

### OpenRouter Fallback
When OpenAI returns 429 (rate limit), the agent automatically retries via OpenRouter using the same model (`gpt-4o`). Uses LangChain's `with_fallbacks()` — zero downtime, same quality.

### Retry with Backoff
All API calls use [tenacity](https://github.com/jd/tenacity) with 3 attempts and exponential backoff for `ConnectError` and `ReadTimeout`.

### Human-in-the-Loop
Write operations (importing activities) require a two-step process:
1. Call `preview_import` to validate and preview the data
2. Call `import_activities` with `confirmed=True` to execute

### Persistent Chat History
Chat threads are stored in PostgreSQL via asyncpg. Each thread has a title (renamable), message history with metadata (tools called, verification status), and timestamps. Auto-deduplicates "New Chat" names.

### Verification Layer
Every response runs through domain-specific checks: numeric consistency (allocation sums), prohibited financial advice detection, and tool-data completeness verification.

### Output Formatter
Responses include data source citations (which Ghostfolio endpoints provided the data) and a confidence level (high/medium/low) based on tool coverage and data quality.

## Evaluation Suite

**[Eval Dataset](data/eval_datasets/sample_queries.json)** | **[Eval Runner](tests/eval/run_eval.py)** | **[Rubric Config](data/eval_datasets/rubric.yaml)** | **[Dataset Docs](data/eval_datasets/README.md)**

70 eval queries across 10 categories, 46 subcategories, and 3 difficulty levels. All checks are **deterministic** (zero API cost, zero ambiguity):

| Check | What it verifies | Example |
|---|---|---|
| **Tool match** | Agent called the correct tool(s) | "What are my holdings?" should call `get_portfolio_holdings` |
| **Keyword match** | Response contains expected terms | Response to holdings query should contain "holdings" or "shares" |
| **Exclusion check** | Response avoids prohibited phrases | Agent should NOT say "I don't know" or "financial advice" |
| **Coverage matrix** | Subcategory x difficulty grid | Shows which areas have test gaps |

### Running Evals

```bash
# Run all 70 queries
python tests/eval/run_eval.py

# Filter by category or difficulty
python tests/eval/run_eval.py --category performance
python tests/eval/run_eval.py --difficulty hard

# Export results to JSON
python tests/eval/run_eval.py --output eval_results.json

# A/B experiment tracking
python tests/eval/run_eval.py --variant new_prompt --output new_prompt.json
```

### Latest Results (87% pass rate)

```
  Tool Match:       61/70 passed (87%)
  Keyword Match:    66/70 passed (94%)
  Exclusion Check:  70/70 passed (100%)
  Total Time:       550.4s (7.9s avg per query)
  Zero 429 rate limit errors (OpenRouter fallback active)
```

**Eval categories:** `portfolio_read`, `performance`, `transaction_history`, `symbol_lookup`, `accounts`, `allocation`, `risk_analysis`, `import`, `system`, `settings`, `multi_tool`

## Ghostfolio Fork Enhancements

**[Forked Repo](https://github.com/s85191939/ghostfolio)**

We added the following endpoints to the Ghostfolio NestJS backend:

### Portfolio Analytics Module (`/api/v1/analytics`)
Server-side computed risk metrics that Ghostfolio doesn't natively provide:
- **Concentration risk** — Herfindahl-Hirschman Index (HHI), top holding identification, high-concentration flag
- **Diversification score** — 0-100 composite score based on holdings breadth, asset class variety, and allocation evenness
- **Asset allocation breakdown** — by asset class with weights and values
- **Auto-generated insights** — human-readable risk warnings and observations

### AI Summary Endpoint (`/api/v1/ai/summary`)
Structured JSON response designed for AI agent consumption:
- Full holdings list with live prices, allocation percentages, asset classes
- Concentration and diversification metrics (computed server-side)
- Insight strings ready for the agent to relay to users
- Base currency and computation timestamp

## Testing

```bash
# Run all unit tests (19 tests)
source .venv/bin/activate
python -m pytest tests/unit -v

# Run integration tests (requires live Ghostfolio)
python -m pytest tests/integration -v -m integration

# Run evaluation suite (see Evaluation Suite above)
python tests/eval/run_eval.py
```

## Deployment

The project is deployed on [Railway](https://railway.app) with 4 services:

| Service | Description |
|---|---|
| **Agent** (lovely-vitality) | FastAPI + LangGraph agent (Python 3.11) |
| **Ghostfolio** | Wealth management app (NestJS + Angular, Docker image) |
| **PostgreSQL** | Database for Ghostfolio + chat persistence |
| **Redis** | Cache/session store for Ghostfolio |

## Project Structure

```
AgentForge/
├── agent/
│   ├── config/
│   │   └── settings.py        # Pydantic settings (env vars)
│   ├── core/
│   │   ├── agent.py           # LangGraph ReAct agent + OpenRouter fallback
│   │   ├── client.py          # Ghostfolio HTTP client (auto-auth, retry)
│   │   ├── database.py        # PostgreSQL chat persistence (asyncpg)
│   │   ├── verification.py    # Domain-specific response verification
│   │   └── formatter.py       # Output formatter (citations + confidence)
│   ├── tools/
│   │   ├── __init__.py        # ALL_TOOLS export (11 tools)
│   │   ├── auth.py            # authenticate, health_check
│   │   ├── portfolio.py       # holdings, performance, details
│   │   ├── orders.py          # get_orders, preview_import, import_activities
│   │   ├── accounts.py        # get_accounts
│   │   ├── symbols.py         # lookup_symbol
│   │   └── user.py            # get_user_settings
│   ├── static/
│   │   └── index.html         # Chat web UI (debug panel, ticker, threads)
│   ├── main.py                # FastAPI server
│   └── cli.py                 # Interactive CLI
├── tests/
│   ├── unit/                  # 19 unit tests (mocked API)
│   ├── integration/           # E2E tests (live Ghostfolio)
│   └── eval/
│       └── run_eval.py        # Eval runner (binary checks + coverage matrix)
├── data/eval_datasets/
│   ├── sample_queries.json    # 70 eval queries (10 categories, 3 difficulties)
│   └── rubric.yaml            # Rubric config with anchored score definitions
├── scripts/
│   └── seed_data.py           # Seed demo portfolio (9 transactions)
├── docker/
│   └── docker-compose.yml     # Ghostfolio + PostgreSQL + Redis
├── Dockerfile                 # Agent service container
├── railway.toml               # Railway deployment config
└── pyproject.toml             # Python project config
```

## License

MIT
