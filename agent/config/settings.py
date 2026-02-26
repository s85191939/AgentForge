"""Application settings loaded from environment variables."""

from __future__ import annotations

import logging
import os

from pydantic import field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger("agentforge.settings")

# ---------------------------------------------------------------------------
# Production environment detection
# ---------------------------------------------------------------------------

_PRODUCTION_ENV_MARKERS = (
    "RAILWAY_ENVIRONMENT",
    "RAILWAY_SERVICE_NAME",
    "RAILWAY_PROJECT_ID",
    "FLY_APP_NAME",
    "RENDER_SERVICE_ID",
    "HEROKU_APP_NAME",
)


def _is_production() -> bool:
    """Return True when running inside a known production platform."""
    return any(os.getenv(marker) for marker in _PRODUCTION_ENV_MARKERS)


def _is_testing() -> bool:
    """Return True when the testing bypass flag is set."""
    return os.getenv("AGENTFORGE_TESTING") == "1"


class Settings(BaseSettings):
    """Global configuration for the AgentForge Finance agent."""

    # Ghostfolio
    ghostfolio_base_url: str = "http://localhost:3333"
    ghostfolio_security_token: str = ""

    # OpenAI / LLM (supports OpenRouter via base_url override)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_base_url: str = ""  # Set to "https://openrouter.ai/api/v1" for OpenRouter

    # OpenRouter fallback (used when OpenAI rate-limits)
    openrouter_api_key: str = ""  # Set to enable automatic fallback on 429

    # LangSmith
    langchain_tracing_v2: bool = True
    langchain_api_key: str = ""
    langchain_project: str = "agentforge-finance"

    # Finnhub (financial news — free tier: 60 calls/min)
    finnhub_api_key: str = ""  # Set in .env or Railway config

    # Database (shared Ghostfolio Postgres — for chat persistence)
    database_url: str = ""

    # Agent
    agent_max_iterations: int = 10
    agent_confidence_threshold: float = 0.7

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("ghostfolio_security_token")
    @classmethod
    def security_token_not_empty(cls, v: str) -> str:
        if _is_testing():
            # BLOCK testing mode in production — hard gate
            if _is_production():
                raise ValueError(
                    "AGENTFORGE_TESTING=1 is FORBIDDEN in production environments. "
                    "Remove this env var from Railway/Fly/Render/Heroku config."
                )
            return v
        if not v or v == "your-security-token-here":
            raise ValueError(
                "GHOSTFOLIO_SECURITY_TOKEN must be set in .env. "
                "See README for setup instructions."
            )
        return v

    @field_validator("openai_api_key")
    @classmethod
    def openai_key_not_empty(cls, v: str) -> str:
        if _is_testing():
            if _is_production():
                raise ValueError(
                    "AGENTFORGE_TESTING=1 is FORBIDDEN in production environments. "
                    "Remove this env var from Railway/Fly/Render/Heroku config."
                )
            return v
        if not v or v.startswith("your-"):
            raise ValueError("OPENAI_API_KEY must be set in .env.")
        return v


settings = Settings()

# Warn loudly at import time if testing flag is active
if _is_testing():
    logger.warning(
        "⚠ AGENTFORGE_TESTING=1 is active — validator shortcuts enabled. "
        "This must NEVER be set in production."
    )
