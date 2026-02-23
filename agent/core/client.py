"""HTTP client for the Ghostfolio REST API."""

from __future__ import annotations

import httpx

from agent.config.settings import settings


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
        response = await self._http.post(
            "/api/v1/auth/anonymous",
            json={"accessToken": self._security_token},
        )
        response.raise_for_status()
        self._jwt = response.json()["authToken"]
        return self._jwt

    @property
    def _headers(self) -> dict[str, str]:
        if self._jwt is None:
            raise RuntimeError("Not authenticated — call authenticate() first.")
        return {"Authorization": f"Bearer {self._jwt}"}

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
        r = await self._http.get("/api/v1/portfolio/holdings", headers=self._headers)
        r.raise_for_status()
        return r.json()

    async def get_portfolio_performance(self, range_: str = "max") -> dict:
        """GET /api/v1/portfolio/performance?range=<range>

        Valid ranges: 1d, wtd, 1w, mtd, 1m, 3m, ytd, 1y, 3y, 5y, max
        """
        r = await self._http.get(
            "/api/v1/portfolio/performance",
            headers=self._headers,
            params={"range": range_},
        )
        r.raise_for_status()
        return r.json()

    async def get_portfolio_details(self, range_: str = "max") -> dict:
        """GET /api/v1/portfolio/details?range=<range>"""
        r = await self._http.get(
            "/api/v1/portfolio/details",
            headers=self._headers,
            params={"range": range_},
        )
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Orders / Activities
    # ------------------------------------------------------------------

    async def get_orders(self) -> dict:
        """GET /api/v1/order"""
        r = await self._http.get("/api/v1/order", headers=self._headers)
        r.raise_for_status()
        return r.json()

    async def import_activities(self, activities: list[dict]) -> dict:
        """POST /api/v1/import — import a list of activity objects."""
        r = await self._http.post(
            "/api/v1/import",
            headers=self._headers,
            json={"activities": activities},
        )
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Accounts
    # ------------------------------------------------------------------

    async def get_accounts(self) -> dict:
        """GET /api/v1/account"""
        r = await self._http.get("/api/v1/account", headers=self._headers)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Symbols / Market Data
    # ------------------------------------------------------------------

    async def lookup_symbol(self, query: str) -> dict:
        """GET /api/v1/symbol/lookup?query=<query>"""
        r = await self._http.get(
            "/api/v1/symbol/lookup",
            headers=self._headers,
            params={"query": query},
        )
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # User
    # ------------------------------------------------------------------

    async def get_user(self) -> dict:
        """GET /api/v1/user"""
        r = await self._http.get("/api/v1/user", headers=self._headers)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        await self._http.aclose()
