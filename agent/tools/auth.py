"""Authentication and health-check tools."""

from __future__ import annotations

from langchain_core.tools import tool

from agent.core.client import GhostfolioClient

# Module-level client instance — initialised by the agent on startup.
_client: GhostfolioClient | None = None


def set_client(client: GhostfolioClient) -> None:
    global _client
    _client = client


def get_client() -> GhostfolioClient:
    if _client is None:
        raise RuntimeError("GhostfolioClient has not been initialised.")
    return _client


@tool
async def authenticate() -> str:
    """Authenticate with the Ghostfolio instance.

    Exchanges the configured security token for a JWT bearer token.
    Must be called before using any other portfolio tools.

    Returns a confirmation message.
    """
    client = get_client()
    jwt = await client.authenticate()
    return f"Authenticated successfully. JWT starts with: {jwt[:12]}..."


@tool
async def health_check() -> str:
    """Check if the Ghostfolio instance is running and healthy.

    Returns the health status of the Ghostfolio server.
    Does not require authentication.
    """
    client = get_client()
    result = await client.health_check()
    return f"Ghostfolio status: {result.get('status', 'UNKNOWN')}"
