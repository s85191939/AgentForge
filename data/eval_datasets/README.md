# AgentForge Finance Eval Dataset

A public evaluation dataset for benchmarking AI financial portfolio agents. Designed for agents that interact with portfolio management APIs (e.g., Ghostfolio) through tool-calling LLMs.

## Overview

| Metric | Value |
|--------|-------|
| Total queries | 70 |
| Categories | 11 |
| Difficulty levels | Easy, Medium, Hard |
| Format | JSON |
| License | MIT |

## Categories

| Category | Count | Description |
|----------|-------|-------------|
| `portfolio_read` | 10 | Holdings retrieval and position queries |
| `performance` | 11 | Time-range performance and return queries |
| `transaction_history` | 9 | Order history, filtering, aggregation |
| `symbol_lookup` | 8 | Ticker/symbol resolution from company names |
| `allocation` | 6 | Asset class and sector breakdown |
| `risk_analysis` | 6 | Concentration, diversification, rebalancing |
| `accounts` | 4 | Account listing and comparison |
| `import` | 4 | Transaction recording with safety preview |
| `system` | 2 | Health checks and connectivity |
| `settings` | 2 | User preferences and configuration |
| `multi_tool` | 3 | Queries requiring 2+ tool calls |

## Schema

Each eval entry contains:

```json
{
  "id": "eval_001",
  "query": "What are my current holdings?",
  "expected_tools": ["get_portfolio_holdings"],
  "expected_params": {"range": "ytd"},
  "category": "portfolio_read",
  "difficulty": "easy",
  "expected_response_contains": ["holdings", "shares"],
  "description": "Basic portfolio holdings retrieval"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique identifier (eval_NNN) |
| `query` | string | yes | Natural language user query |
| `expected_tools` | string[] | yes | Tools the agent should call |
| `expected_params` | object | no | Expected parameters for tool calls |
| `category` | string | yes | Query category for analysis |
| `difficulty` | string | yes | easy, medium, or hard |
| `expected_response_contains` | string[] | no | Keywords the response should contain |
| `description` | string | yes | Human-readable description of what is tested |

## Tools Reference

These are the tools an agent is expected to have access to:

| Tool | Description |
|------|-------------|
| `get_portfolio_holdings` | Retrieve current positions and values |
| `get_portfolio_performance` | Get returns over a time range |
| `get_portfolio_details` | Detailed breakdown (allocation, sectors) |
| `get_orders` | Transaction history (buys, sells, dividends) |
| `lookup_symbol` | Search for ticker symbols by company name |
| `get_accounts` | List investment accounts |
| `preview_import` | Preview a transaction before importing |
| `import_activities` | Execute a confirmed transaction import |
| `health_check` | Check backend API connectivity |
| `get_user_settings` | Retrieve user preferences |

## Usage

### With the built-in eval runner

```bash
# Requires running Ghostfolio instance + OPENAI_API_KEY
python tests/eval/run_eval.py
```

### Load the dataset in Python

```python
import json

with open("data/eval_datasets/sample_queries.json") as f:
    queries = json.load(f)

# Filter by category
performance_queries = [q for q in queries if q["category"] == "performance"]

# Filter by difficulty
hard_queries = [q for q in queries if q["difficulty"] == "hard"]

# Get multi-tool queries
multi_tool = [q for q in queries if len(q["expected_tools"]) > 1]
```

### Scoring

The eval runner scores on two criteria:

1. **Tool Match**: Did the agent call the expected tools? (subset check)
2. **Has Response**: Did the agent produce a non-empty final response?

A query passes if both criteria are met. The overall score is `passed / total`.

For richer evaluation, use the `expected_response_contains` field to check for keyword presence in the agent's response.

## What This Tests

- **Tool selection accuracy**: Does the agent pick the right tool for each query?
- **Parameter extraction**: Does the agent parse dates, ranges, and tickers correctly?
- **Multi-tool orchestration**: Can the agent chain multiple tools for complex queries?
- **Natural language understanding**: Can the agent handle slang, abbreviations, non-English input?
- **Financial reasoning**: Can the agent interpret allocation, risk, and performance concepts?

## Contributing

To add new eval queries:

1. Add entries to `sample_queries.json` following the schema above
2. Use the next available `eval_NNN` ID
3. Include all required fields
4. Test with the eval runner to verify the query works

## Citation

If you use this dataset in your research or projects:

```
AgentForge Finance Eval Dataset
https://github.com/s85191939/AgentForge
License: MIT
```
