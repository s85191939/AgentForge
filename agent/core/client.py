"""HTTP client for the Ghostfolio REST API."""

from __future__ import annotations

import logging

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agent.config.settings import settings

logger = logging.getLogger("agentforge.client")

# Retry policy: 3 attempts with exponential backoff (1s → 10s)
_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout)),
    reraise=True,
)


class GhostfolioClient:
    """Async HTTP client that handles auth and requests to Ghostfolio."""

    def __init__(
        self,
        base_url: str | None = None,
        security_token: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.ghostfolio_base_url).rstrip("/")
        self._security_token = security_token or settings.ghostfolio_security_token
        self._jwt: str | None = None
        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def authenticate(self) -> str:
        """Exchange the security token for a JWT bearer token.

        Returns the JWT string.
        """
        logger.info("Authenticating with Ghostfolio...")
        response = await self._http.post(
            "/api/v1/auth/anonymous",
            json={"accessToken": self._security_token},
        )
        response.raise_for_status()
        self._jwt = response.json()["authToken"]
        logger.info("Authenticated successfully.")
        return self._jwt

    async def _ensure_authenticated(self) -> None:
        """Authenticate if no JWT is present."""
        if self._jwt is None:
            await self.authenticate()

    async def _get_headers(self) -> dict[str, str]:
        """Return auth headers, auto-authenticating if needed."""
        await self._ensure_authenticated()
        return {"Authorization": f"Bearer {self._jwt}"}

    # ------------------------------------------------------------------
    # Centralized request helper (retry + 401 re-auth)
    # ------------------------------------------------------------------

    @_retry
    async def _request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> httpx.Response:
        """Make an authenticated request with retry and 401 re-auth.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            url: API path (e.g., /api/v1/portfolio/holdings).
            **kwargs: Passed to httpx (params, json, etc.).
        """
        headers = await self._get_headers()
        r = await self._http.request(method, url, headers=headers, **kwargs)

        # If 401, clear JWT, re-authenticate, and retry once
        if r.status_code == 401:
            logger.warning("Received 401 — re-authenticating...")
            self._jwt = None
            headers = await self._get_headers()
            r = await self._http.request(method, url, headers=headers, **kwargs)

        r.raise_for_status()
        return r

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_check(self) -> dict:
        """GET /api/v1/health — returns {"status": "OK"} if healthy."""
        r = await self._http.get("/api/v1/health")
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Portfolio
    # ------------------------------------------------------------------

    async def get_portfolio_holdings(self) -> dict:
        """GET /api/v1/portfolio/holdings"""
        r = await self._request("GET", "/api/v1/portfolio/holdings")
        return r.json()

    async def get_portfolio_performance(self, range_: str = "max") -> dict:
        """GET /api/v2/portfolio/performance?range=<range>

        Valid ranges: 1d, wtd, 1w, mtd, 1m, 3m, ytd, 1y, 3y, 5y, max
        """
        # v2 endpoint (v1 was removed in newer Ghostfolio versions)
        r = await self._request(
            "GET",
            "/api/v2/portfolio/performance",
            params={"range": range_},
        )
        return r.json()

    async def get_portfolio_details(self, range_: str = "max") -> dict:
        """GET /api/v1/portfolio/details?range=<range>"""
        r = await self._request(
            "GET",
            "/api/v1/portfolio/details",
            params={"range": range_},
        )
        return r.json()

    # ------------------------------------------------------------------
    # Orders / Activities
    # ------------------------------------------------------------------

    async def get_orders(self) -> dict:
        """GET /api/v1/order"""
        r = await self._request("GET", "/api/v1/order")
        return r.json()

    async def import_activities(self, activities: list[dict]) -> dict:
        """POST /api/v1/import — import a list of activity objects."""
        r = await self._request(
            "POST",
            "/api/v1/import",
            json={"activities": activities},
        )
        return r.json()

    async def delete_order(self, order_id: str) -> None:
        """DELETE /api/v1/order/:id — remove a single activity/order."""
        await self._request("DELETE", f"/api/v1/order/{order_id}")

    # ------------------------------------------------------------------
    # Accounts
    # ------------------------------------------------------------------

    async def get_accounts(self) -> dict:
        """GET /api/v1/account"""
        r = await self._request("GET", "/api/v1/account")
        return r.json()

    # ------------------------------------------------------------------
    # Symbols / Market Data
    # ------------------------------------------------------------------

    async def lookup_symbol(self, query: str) -> dict:
        """GET /api/v1/symbol/lookup?query=<query>"""
        r = await self._request(
            "GET",
            "/api/v1/symbol/lookup",
            params={"query": query},
        )
        return r.json()

    # ------------------------------------------------------------------
    # User
    # ------------------------------------------------------------------

    async def get_user(self) -> dict:
        """GET /api/v1/user"""
        r = await self._request("GET", "/api/v1/user")
        return r.json()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        await self._http.aclose()
