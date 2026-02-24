# AI Cost Analysis

## 1. Development Spend

### LLM API Costs (Development Phase)

| Provider | Model | Usage | Estimated Cost |
|---|---|---|---|
| OpenAI | GPT-4o | Agent development, testing, iteration (~50 queries during dev) | ~$1.50 |
| OpenAI | GPT-4o | Eval suite runs (10 queries x ~3 runs) | ~$0.90 |
| OpenAI | GPT-4o | Live deployment testing & demo (~20 queries) | ~$0.60 |
| **Total LLM** | | | **~$3.00** |

### Infrastructure Costs (Development Phase)

| Service | Provider | Duration | Cost |
|---|---|---|---|
| Railway Starter Plan | Railway | Trial / free tier | $0.00 |
| PostgreSQL (managed) | Railway | Included in plan | $0.00 |
| Redis (managed) | Railway | Included in plan | $0.00 |
| Ghostfolio (Docker) | Railway | Included in plan | $0.00 |
| **Total Infra** | | | **$0.00** |

### Tool/Service Costs

| Tool | Cost |
|---|---|
| GitHub (public repo) | $0.00 |
| LangSmith (free tier) | $0.00 |
| **Total Tools** | **$0.00** |

### Total Development Cost: ~$3.00

## 2. Per-Query Cost Breakdown

Each user query to the agent incurs the following costs:

| Component | Cost | Notes |
|---|---|---|
| GPT-4o input tokens | ~$0.0025 | System prompt (~500 tokens) + user message + tool results |
| GPT-4o output tokens | ~$0.01 | Agent reasoning + formatted response |
| Tool call overhead | ~$0.005 | Additional LLM call per tool invocation (1-3 tools/query) |
| Ghostfolio API | $0.00 | Self-hosted, no per-call cost |
| **Total per query** | **~$0.015 - $0.03** | |

### Token Usage Estimates (per query)

| Stage | Input Tokens | Output Tokens |
|---|---|---|
| System prompt | ~500 | 0 |
| User message | ~20-50 | 0 |
| Tool call decision | ~100 | ~50 |
| Tool result processing | ~200-1000 | 0 |
| Final response | ~100 | ~200-500 |
| **Total** | **~920 - 1650** | **~250 - 550** |

GPT-4o pricing (as of Feb 2026): $2.50/1M input tokens, $10.00/1M output tokens.

## 3. Monthly Projections

### Scenario 1: Personal Use (1 user, light usage)

| Metric | Value |
|---|---|
| Queries/day | ~5 |
| Queries/month | ~150 |
| LLM cost/month | ~$3.00 |
| Infrastructure/month | ~$5.00 (Railway hobby) |
| **Total/month** | **~$8.00** |

### Scenario 2: Small Team (5 users, moderate usage)

| Metric | Value |
|---|---|
| Queries/day | ~25 |
| Queries/month | ~750 |
| LLM cost/month | ~$15.00 |
| Infrastructure/month | ~$10.00 (Railway pro) |
| **Total/month** | **~$25.00** |

### Scenario 3: Production (50 users, active usage)

| Metric | Value |
|---|---|
| Queries/day | ~200 |
| Queries/month | ~6,000 |
| LLM cost/month | ~$120.00 |
| Infrastructure/month | ~$30.00 (Railway pro + scaling) |
| **Total/month** | **~$150.00** |

## 4. Cost Optimization Strategies

1. **Model selection**: Switch to `gpt-4o-mini` for simple queries (~10x cheaper) while keeping `gpt-4o` for complex analysis. Could implement a query classifier to route appropriately.

2. **Response caching**: Cache tool results for identical queries within a short TTL (e.g., 60s). Portfolio data doesn't change frequently.

3. **Prompt optimization**: Compress the system prompt and use few-shot examples selectively. Current system prompt is ~500 tokens which is already reasonably compact.

4. **Token limits**: Set `max_tokens` on the LLM response to prevent runaway generation. Current recursion limit already bounds the number of tool calls.

5. **Batch processing**: For eval runs and bulk analysis, batch queries to reduce overhead.

## 5. Break-Even Analysis

At the current per-query cost of ~$0.02:

- **$5/month budget** supports ~250 queries/month (~8/day)
- **$20/month budget** supports ~1,000 queries/month (~33/day)
- **$50/month budget** supports ~2,500 queries/month (~83/day)

The main cost driver is the OpenAI API. Infrastructure costs on Railway are relatively fixed and low. Switching to a self-hosted LLM (e.g., Llama 3) would eliminate the per-query LLM cost but requires GPU infrastructure ($50-200/month for a capable instance).
