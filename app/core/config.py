"""
Application configuration using pydantic-settings.

Uses singleton pattern via lru_cache to ensure Settings are loaded once.
Configuration values are read from .env file or environment variables.
"""

from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    # Application
    app_name: str = "Enterprise AI Knowledge Copilot"
    app_version: str = "1.0.0"
    service_name: str = "enterprise-ai-agent-platform"
    debug: bool = False
    environment: str = "development"
    log_level: str = "INFO"
    log_json_format: bool = True

    # Database (SQLite for dev, PostgreSQL for production)
    database_url: str = "sqlite+aiosqlite:///./knowledge.db"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "knowledge_copilot"
    postgres_user: str = "postgres"
    postgres_password: str = ""
    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379

    # ChromaDB Vector Store
    chroma_host: str = ""
    chroma_port: int = 8000
    chroma_path: str = "./data/chroma"
    chroma_collection: str = "knowledge_docs"

    # LLM Client (for AI-powered analysis features)
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"

    # Embedding Model (for semantic search)
    embedding_model: str = "text-embedding-ada-002"
    embedding_api_base: str = ""  # defaults to llm_base_url
    embedding_api_key: str = ""  # defaults to llm_api_key
    embedding_dimension: int = 1536

    # Knowledge Base
    knowledge_base_dir: str = "./data/knowledge"
    upload_dir: str = "./data/uploads"

    # Sync Configuration
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    yuque_token: str = ""

    # Integration (Project 1 - AI DevOps Assistant)
    project1_api_base: str = "http://localhost:8000"
    project1_api_key: str = ""

    # Integration (Project 2 - Enterprise DevOps MCP Server)
    project2_mcp_path: str = ""

    # MCP (Managed Cloud Provider / Model Context Protocol) Settings
    mcp_server_url: str = ""
    """URL of a generic MCP tool server for remote tool discovery."""
    enterprise_devops_mcp_url: str = ""
    """URL of the Enterprise DevOps MCP Server (Project 2)."""
    mcp_api_key: str = ""
    """Optional API key for authenticating with the MCP server."""
    mcp_discover_on_startup: bool = True
    """Whether to auto-discover MCP tools on application startup."""

    # Security / JWT
    jwt_secret: str = "dev-secret-do-not-use-in-production"
    jwt_expiration_minutes: int = 60
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost"
    rate_limit_per_minute: int = 120

    # Observability
    otel_exporter_otlp_endpoint: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def model_post_init(self, __context: Any) -> None:
        """Reject weak JWT secrets in production; warn otherwise."""
        import logging

        weak = {
            "dev-secret-do-not-use-in-production",
            "change-me-in-production",
            "secret",
            "",
        }
        env = (self.environment or "development").lower()
        if env in {"production", "prod"} and self.jwt_secret in weak:
            raise ValueError("JWT_SECRET must be set to a strong value when ENVIRONMENT=production")
        if self.jwt_secret in weak and not self.debug:
            logging.getLogger(__name__).warning(
                "JWT_SECRET is using an insecure default. "
                "Set JWT_SECRET via .env for any shared or production deployment."
            )


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
