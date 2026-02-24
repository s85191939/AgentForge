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

## Architecture

```
Browser / CLI
     |
     v
 FastAPI Server (Python)
     |
     v
 LangGraph ReAct Agent (GPT-4o)
     |
     v
 Ghostfolio REST API
     |
     v
 PostgreSQL + Redis
```

The agent runs as a **separate service** that communicates with Ghostfolio via its REST API. This architecture avoids AGPL-3.0 license obligations and leverages Python's AI/ML ecosystem.

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
| `LANGCHAIN_TRACING_V2` | No | Enable LangSmith tracing (default: `true`) |
| `LANGCHAIN_API_KEY` | No | LangSmith API key for observability |
| `LANGCHAIN_PROJECT` | No | LangSmith project name (default: `agentforge-finance`) |

### Getting a Ghostfolio Security Token

1. Open your Ghostfolio instance in a browser
2. Go to **Settings** (gear icon)
3. Under **Security Token**, copy the token
4. Paste it as `GHOSTFOLIO_SECURITY_TOKEN` in your `.env`

## Usage

### Web UI

Navigate to `http://localhost:8000` (local) or the [live URL](https://lovely-vitality-production-fdc1.up.railway.app). The chat interface includes:

- Suggestion buttons for common queries
- Health status indicator (green = Ghostfolio connected)
- Multi-turn conversation memory per thread
- Markdown-formatted responses

### CLI

```bash
source .venv/bin/activate
python -m agent.cli
```

Type natural language queries and press Enter. Type `quit` or `exit` to stop.

### API (cURL)

```bash
# Health check
curl https://lovely-vitality-production-fdc1.up.railway.app/health

# Query the agent
curl -X POST https://lovely-vitality-production-fdc1.up.railway.app/query \
  -H 'Content-Type: application/json' \
  -d '{"message": "What are my holdings?", "thread_id": "my-session"}'
```

### Example Queries

- "What are my current holdings?"
- "Show me my portfolio performance"
- "How much AAPL do I own?"
- "List my recent transactions"
- "Look up the symbol for Tesla"
- "What is my portfolio allocation?"

## Project Structure

```
AgentForge/
├── agent/
│   ├── config/
│   │   └── settings.py        # Pydantic settings (env vars)
│   ├── core/
│   │   ├── agent.py           # LangGraph ReAct agent + AsyncSqliteSaver
│   │   ├── client.py          # Ghostfolio HTTP client (auto-auth, retry)
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
│   │   └── index.html         # Chat web UI
│   ├── main.py                # FastAPI server
│   └── cli.py                 # Interactive CLI
├── tests/
│   ├── unit/                  # 19 unit tests (mocked API)
│   ├── integration/           # E2E tests (live Ghostfolio)
│   └── eval/                  # Agent evaluation suite
├── scripts/
│   └── seed_data.py           # Seed demo portfolio (9 transactions)
├── data/eval_datasets/        # Evaluation query datasets
├── docker/
│   └── docker-compose.yml     # Ghostfolio + PostgreSQL + Redis
├── Dockerfile                 # Agent service container
├── railway.toml               # Railway deployment config
└── pyproject.toml             # Python project config
```

## Agent Tools

| Tool | Description | Read/Write |
|---|---|---|
| `authenticate` | Authenticate with Ghostfolio (auto-called) | Read |
| `health_check` | Check Ghostfolio connectivity | Read |
| `get_portfolio_holdings` | List all portfolio holdings | Read |
| `get_portfolio_performance` | Get portfolio performance metrics | Read |
| `get_portfolio_details` | Get detailed portfolio breakdown | Read |
| `get_orders` | List transaction history | Read |
| `preview_import` | Preview activities before importing | Read |
| `import_activities` | Import activities (requires `confirmed=True`) | Write |
| `get_accounts` | List investment accounts | Read |
| `lookup_symbol` | Search for stock/ETF symbols | Read |
| `get_user_settings` | Get user preferences | Read |

## Key Features

### Auto-Authentication
The HTTP client automatically authenticates on the first API call and re-authenticates on 401 responses. No manual auth step needed.

### Retry with Backoff
All API calls use [tenacity](https://github.com/jd/tenacity) with 3 attempts and exponential backoff for `ConnectError` and `ReadTimeout`.

### Human-in-the-Loop
Write operations (importing activities) require a two-step process:
1. Call `preview_import` to validate and preview the data
2. Call `import_activities` with `confirmed=True` to execute

### Persistent Memory
Uses LangGraph's `AsyncSqliteSaver` checkpointer backed by SQLite — conversation history persists across server restarts. Each `thread_id` maintains its own isolated conversation history.

### Verification Layer
Every response runs through domain-specific checks: numeric consistency (allocation sums), prohibited financial advice detection, and tool-data completeness verification.

### Output Formatter
Responses include data source citations (which Ghostfolio endpoints provided the data) and a confidence level (high/medium/low) based on tool coverage and data quality.

## Core Agent Architecture

| Component | Status | Description |
|---|---|---|
| **Reasoning Engine** | LangGraph ReAct | GPT-4o with autonomous reason-act-observe loop |
| **Tool Registry** | 11 tools | Auto-discovered, type-safe Ghostfolio API tools |
| **Memory System** | SQLite persistent | Cross-session conversation history via `AsyncSqliteSaver` |
| **Orchestrator** | FastAPI | Async HTTP server with middleware, error handling, health checks |
| **Verification Layer** | 3 check types | Numeric consistency, prohibited advice, tool-data completeness |
| **Output Formatter** | Citations + confidence | Data source attribution and confidence estimation |

## Evaluation Suite

The eval dataset (`data/eval_datasets/sample_queries.json`) contains **70 queries** across 9 categories with difficulty ratings. See the [Eval Dataset README](data/eval_datasets/README.md) for full schema documentation.

```bash
# Run all evaluations
python tests/eval/run_eval.py

# Filter by category or difficulty
python tests/eval/run_eval.py --category performance
python tests/eval/run_eval.py --difficulty hard

# Export results to JSON
python tests/eval/run_eval.py --output eval_results.json
```

**Eval categories:** `portfolio_read`, `performance`, `transactions`, `search`, `accounts`, `import`, `general`, `edge_case`, `multi_tool`

**Scoring:** Tool match accuracy (did the agent call the right tools?) + keyword match (does the response contain expected terms?) + latency tracking.

## Testing

```bash
# Run all unit tests (19 tests)
source .venv/bin/activate
python -m pytest tests/unit -v

# Run integration tests (requires live Ghostfolio)
python -m pytest tests/integration -v -m integration

# Run evaluation suite (see above)
python tests/eval/run_eval.py
```

## Deployment

The project is deployed on [Railway](https://railway.app) with 4 services:

| Service | Description |
|---|---|
| **Agent** (lovely-vitality) | FastAPI + LangGraph agent |
| **Ghostfolio** | Wealth management app (Docker image) |
| **PostgreSQL** | Database for Ghostfolio |
| **Redis** | Cache/session store for Ghostfolio |

### Deploy your own

1. Install the [Railway CLI](https://docs.railway.app/guides/cli)
2. `railway login`
3. `railway init` to create a project
4. Add PostgreSQL and Redis databases
5. Add Ghostfolio service with `ghostfolio/ghostfolio:latest` image
6. Set environment variables (see Configuration above)
7. Deploy the agent: `railway up`

## Tech Stack

- **Agent Framework:** LangChain + LangGraph (ReAct agent pattern)
- **LLM:** OpenAI GPT-4o (configurable)
- **API Server:** FastAPI + Uvicorn
- **HTTP Client:** httpx (async) + tenacity (retry)
- **Config:** Pydantic Settings (with field validators)
- **Observability:** LangSmith
- **Target App:** Ghostfolio (self-hosted, Docker)
- **Deployment:** Railway (multi-service)
- **Testing:** pytest + pytest-asyncio + respx

## License

MIT
