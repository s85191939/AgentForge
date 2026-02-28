# AgentForge Bounty: Financial News & Sentiment for Portfolio Holdings

## Customer

Self-directed retail investors who hold 5-15 stocks and currently check news
manually across multiple sites (Yahoo Finance, Bloomberg, CNBC, etc.) to
understand what is moving their portfolio. They want a single conversational
interface that surfaces relevant news automatically.

## Feature

**Portfolio-aware financial news with sentiment analysis and user-created
alerts**, integrated directly into Ghostfolio and accessible through the
AgentForge AI agent.

The agent can:

1. **Fetch news for the entire portfolio** — asks Ghostfolio, which calls the
   Finnhub Company News API, caches results in Postgres, and returns articles
   with headline, source, sentiment, and date.
2. **Fetch news for a single symbol** — same pipeline, scoped to one ticker.
3. **Create news alerts** — user tells the agent "watch TSLA for earnings news"
   and a persistent alert is stored in Ghostfolio's database.
4. **List alerts** — view all monitored symbols and keywords.
5. **Delete alerts** — stop monitoring a symbol.

### Data Flow

```
User → AgentForge (Python) → Ghostfolio API (NestJS) → Finnhub API
                                      ↓
                              Postgres (cached articles + alerts)
```

The agent never calls Finnhub directly. All data flows through Ghostfolio's
REST API, and all stateful data is stored in Ghostfolio's Postgres database.

## Data Source

**Finnhub Company News API** — https://finnhub.io/docs/api/company-news

- Free tier: 60 API calls per minute, no credit card required
- Returns: headline, summary, source, URL, datetime for each article
- Coverage: US equities, ETFs, major international stocks
- Freshness: real-time news updates

Articles are cached in Ghostfolio's Postgres for 1 hour to minimize API calls.

## Stateful Data (CRUD)

Two new tables in Ghostfolio's Postgres database:

### `news_articles` (cache)

| Column       | Type        | Description                    |
|-------------|-------------|--------------------------------|
| id          | TEXT (UUID) | Primary key                    |
| symbol      | TEXT        | Ticker symbol                  |
| headline    | TEXT        | Article headline               |
| summary     | TEXT        | Article summary                |
| sentiment   | TEXT        | positive / negative / neutral  |
| source      | TEXT        | News source name               |
| url         | TEXT        | Article URL                    |
| published_at| TIMESTAMPTZ | Publication date               |
| fetched_at  | TIMESTAMPTZ | When we cached it              |

### `news_alerts` (user-created, full CRUD)

| Column     | Type        | Description                     |
|-----------|-------------|---------------------------------|
| id        | TEXT (UUID) | Primary key                     |
| user_id   | TEXT        | Ghostfolio user ID (FK)         |
| symbol    | TEXT        | Ticker to monitor               |
| keywords  | TEXT        | Optional keyword filter         |
| is_active | BOOLEAN     | Whether alert is active         |
| created_at| TIMESTAMPTZ | Creation timestamp              |
| updated_at| TIMESTAMPTZ | Last modification timestamp     |

**CRUD Operations exposed as Ghostfolio REST endpoints:**

- `POST /api/v1/news/alerts` — Create alert
- `GET /api/v1/news/alerts` — Read all alerts
- `PATCH /api/v1/news/alerts/:id` — Update alert
- `DELETE /api/v1/news/alerts/:id` — Delete alert

All endpoints are JWT-authenticated and user-scoped.

## Impact

1. **Time saved** — Investors no longer manually check 5-15 tickers across
   multiple news sites. One question ("What's the news on my portfolio?")
   replaces 10+ manual lookups.

2. **Proactive awareness** — Alerts let users set up persistent monitoring
   without having to remember to check. The data stays in Ghostfolio and
   persists across sessions.

3. **Sentiment at a glance** — Each article is tagged positive/negative/neutral
   using keyword-based classification, giving users a quick read on whether
   news is favorable or unfavorable.

4. **Integrated experience** — News data flows through Ghostfolio's existing
   auth and API infrastructure. No separate accounts, no context switching,
   no additional credentials.

## Files Changed

### Ghostfolio Fork (NestJS)

| File | Purpose |
|------|---------|
| `endpoints/news/news.module.ts` | NestJS module registration |
| `endpoints/news/news.controller.ts` | REST endpoints (6 routes) |
| `endpoints/news/news.service.ts` | Finnhub integration, DB ops, sentiment |
| `endpoints/news/interfaces/news.interface.ts` | TypeScript interfaces |
| `app.module.ts` | Register NewsModule |

### AgentForge (Python)

| File | Purpose |
|------|---------|
| `agent/core/client.py` | 6 new HTTP client methods |
| `agent/tools/news.py` | 6 LangChain tools (including update_news_alert) |
| `agent/tools/__init__.py` | Register news tools |
| `agent/config/settings.py` | Finnhub API key setting |
| `BOUNTY.md` | This file |
