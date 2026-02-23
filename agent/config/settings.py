"""Application settings loaded from environment variables."""

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

    # Agent
    agent_max_iterations: int = 10
    agent_confidence_threshold: float = 0.7

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
