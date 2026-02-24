"""Application settings loaded from environment variables."""

from __future__ import annotations

import os

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global configuration for the AgentForge Finance agent."""

    # Ghostfolio
    ghostfolio_base_url: str = "http://localhost:3333"
    ghostfolio_security_token: str = ""

    # OpenAI / LLM
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # LangSmith
    langchain_tracing_v2: bool = True
    langchain_api_key: str = ""
    langchain_project: str = "agentforge-finance"

    # Firebase
    firebase_project_id: str = "agentforge-86e27"

    # Agent
    agent_max_iterations: int = 10
    agent_confidence_threshold: float = 0.7

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("ghostfolio_security_token")
    @classmethod
    def security_token_not_empty(cls, v: str) -> str:
        # Skip validation during testing
        if os.getenv("AGENTFORGE_TESTING") == "1":
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
        # Skip validation during testing
        if os.getenv("AGENTFORGE_TESTING") == "1":
            return v
        if not v or v.startswith("your-"):
            raise ValueError("OPENAI_API_KEY must be set in .env.")
        return v


settings = Settings()
