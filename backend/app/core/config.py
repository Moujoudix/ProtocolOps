from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./data/ai_scientist.db"
    backend_cors_allow_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    backend_cors_allow_origin_regex: str | None = None

    openai_api_key: str | None = None
    openai_parse_model: str = "gpt-5.4-mini"
    openai_plan_model: str = "gpt-5.5"
    openai_fallback_model: str = "gpt-5.4-mini"

    semantic_scholar_api_key: str | None = None
    protocols_io_token: str | None = None
    tavily_api_key: str | None = None
    consensus_mcp_enabled: bool = False
    consensus_mcp_bridge_url: str | None = "http://127.0.0.1:8765/search"
    consensus_mcp_server_url: str = "https://mcp.consensus.app/mcp"
    consensus_bridge_port: int = 8765
    consensus_bridge_host: str = "127.0.0.1"
    consensus_bridge_home: str | None = None
    run_live_integration: bool = False
    strict_live_mode: bool = False

    request_timeout_seconds: float = Field(default=12.0, ge=1.0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_allow_origins(self) -> list[str]:
        origins = []
        for raw_origin in self.backend_cors_allow_origins.split(","):
            origin = raw_origin.strip()
            if origin:
                origins.append(origin)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
