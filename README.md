# AgentForge Finance

AI-powered financial portfolio intelligence agent for [Ghostfolio](https://github.com/ghostfolio/ghostfolio).

## Overview

AgentForge Finance is a LangChain-based AI agent that connects to a Ghostfolio instance and answers natural language questions about your investment portfolio — holdings, performance, risk exposure, transaction history, and more.

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/s85191939/AgentForge.git
cd AgentForge

# 2. Start Ghostfolio (Docker)
cp .env.example .env  # Edit with your values
docker compose -f docker/docker-compose.yml up -d

# 3. Install the agent
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 4. Run the CLI
python -m agent.cli

# Or start the API server
python -m agent.main
```

## Project Structure

```
AgentForge/
├── agent/
│   ├── config/         # Settings (env vars, defaults)
│   ├── core/           # GhostfolioClient, LangChain agent
│   ├── tools/          # LangChain tools (portfolio, orders, accounts, symbols)
│   ├── main.py         # FastAPI server
│   └── cli.py          # Interactive CLI
├── tests/
│   ├── unit/           # Unit tests (mocked API)
│   ├── integration/    # Integration tests (live Ghostfolio)
│   └── eval/           # Agent evaluation suite
├── docker/             # Docker Compose for Ghostfolio
├── data/eval_datasets/ # Evaluation query datasets
└── .github/workflows/  # CI pipeline
```

## Tech Stack

- **Agent Framework:** LangChain + LangGraph (ReAct agent)
- **LLM:** OpenAI GPT-4o (configurable)
- **API Server:** FastAPI + Uvicorn
- **HTTP Client:** httpx (async)
- **Observability:** LangSmith
- **Target App:** Ghostfolio (self-hosted, Docker)
- **Testing:** pytest + respx

## License

MIT
