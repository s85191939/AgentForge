"""Seed a fresh Ghostfolio instance with a realistic demo portfolio.

Usage:
    python scripts/seed_data.py

Requires GHOSTFOLIO_BASE_URL and GHOSTFOLIO_SECURITY_TOKEN in .env.
"""

from __future__ import annotations

import asyncio
import sys

from agent.core.client import GhostfolioClient

SEED_ACTIVITIES = [
    # --- Tech stocks ---
    {
        "currency": "USD",
        "dataSource": "YAHOO",
        "date": "2023-01-15T00:00:00.000Z",
        "fee": 0,
        "quantity": 20,
        "symbol": "AAPL",
        "type": "BUY",
        "unitPrice": 135.94,
    },
    {
        "currency": "USD",
        "dataSource": "YAHOO",
        "date": "2023-02-10T00:00:00.000Z",
        "fee": 0,
        "quantity": 15,
        "symbol": "MSFT",
        "type": "BUY",
        "unitPrice": 263.77,
    },
    {
        "currency": "USD",
        "dataSource": "YAHOO",
        "date": "2023-03-20T00:00:00.000Z",
        "fee": 0,
        "quantity": 10,
        "symbol": "GOOGL",
        "type": "BUY",
        "unitPrice": 104.00,
    },
    {
        "currency": "USD",
        "dataSource": "YAHOO",
        "date": "2023-09-15T00:00:00.000Z",
        "fee": 0,
        "quantity": 5,
        "symbol": "AMZN",
        "type": "BUY",
        "unitPrice": 139.57,
    },
    {
        "currency": "USD",
        "dataSource": "YAHOO",
        "date": "2024-01-10T00:00:00.000Z",
        "fee": 0,
        "quantity": 3,
        "symbol": "NVDA",
        "type": "BUY",
        "unitPrice": 547.10,
    },
    # --- ETF (broad market) ---
    {
        "currency": "USD",
        "dataSource": "YAHOO",
        "date": "2023-06-01T00:00:00.000Z",
        "fee": 0,
        "quantity": 50,
        "symbol": "VTI",
        "type": "BUY",
        "unitPrice": 211.54,
    },
    # --- Partial sell ---
    {
        "currency": "USD",
        "dataSource": "YAHOO",
        "date": "2024-03-01T00:00:00.000Z",
        "fee": 4.99,
        "quantity": 5,
        "symbol": "AAPL",
        "type": "SELL",
        "unitPrice": 178.22,
    },
    # --- Dividend ---
    {
        "currency": "USD",
        "dataSource": "YAHOO",
        "date": "2024-06-15T00:00:00.000Z",
        "fee": 0,
        "quantity": 15,
        "symbol": "AAPL",
        "type": "DIVIDEND",
        "unitPrice": 0.25,
    },
    # --- Bond ETF for diversification ---
    {
        "currency": "USD",
        "dataSource": "YAHOO",
        "date": "2024-02-01T00:00:00.000Z",
        "fee": 0,
        "quantity": 30,
        "symbol": "BND",
        "type": "BUY",
        "unitPrice": 72.50,
    },
]


async def main() -> None:
    """Seed the Ghostfolio instance with demo portfolio data."""
    print("Seeding Ghostfolio with demo portfolio data...\n")

    client = GhostfolioClient()

    # Health check first
    try:
        health = await client.health_check()
        print(f"Ghostfolio health: {health.get('status', 'unknown')}")
    except Exception as e:
        print(f"ERROR: Cannot reach Ghostfolio — {e}")
        print("Make sure Docker is running: docker compose -f docker/docker-compose.yml up -d")
        await client.close()
        sys.exit(1)

    # Authenticate
    try:
        await client.authenticate()
        print("Authenticated successfully.\n")
    except Exception as e:
        print(f"ERROR: Authentication failed — {e}")
        print("Check your GHOSTFOLIO_SECURITY_TOKEN in .env")
        await client.close()
        sys.exit(1)

    # Import activities
    try:
        await client.import_activities(SEED_ACTIVITIES)
        print(f"Imported {len(SEED_ACTIVITIES)} activities:")
        for act in SEED_ACTIVITIES:
            print(f"  {act['type']:>8} {act['quantity']:>5} {act['symbol']:<6} "
                  f"@ ${act['unitPrice']:>8.2f} on {act['date'][:10]}")
        print(f"\nDone! Portfolio seeded with {len(SEED_ACTIVITIES)} transactions.")
    except Exception as e:
        print(f"ERROR: Import failed — {e}")
        await client.close()
        sys.exit(1)

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
