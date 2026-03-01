"""
Application configuration via pydantic-settings.

Loads from environment variables and .env file. Validates all required
settings at startup — fail fast if misconfigured.

Usage:
    from src.config.settings import get_settings
    settings = get_settings()
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Azure AI Foundry ──────────────────────────────────────
    azure_ai_project_endpoint: str = Field(
        description="Foundry project endpoint URL",
    )
    model_deployment_name: str = Field(
        default="gpt-4o",
        description="Deployed model name in Foundry",
    )

    # ── Azure NetApp Files ────────────────────────────────────
    azure_subscription_id: str = Field(
        description="Azure subscription ID",
    )
    anf_resource_group: str = Field(
        description="Resource group containing ANF account",
    )
    anf_account_name: str = Field(
        description="ANF account name",
    )
    anf_pool_name: str = Field(
        description="Default capacity pool name",
    )

    # ── Observability ─────────────────────────────────────────
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )
    log_format: Literal["json", "text"] = Field(
        default="text",
        description="Log format: 'json' for production, 'text' for development",
    )
    otel_exporter_endpoint: str | None = Field(
        default=None,
        description="OpenTelemetry collector endpoint (optional)",
    )

    # ── Feature Flags ─────────────────────────────────────────
    enable_destructive_ops: bool = Field(
        default=True,
        description="Allow destructive operations (delete snapshot, etc.)",
    )
    max_retry_attempts: int = Field(
        default=3,
        description="Max retry attempts for transient Azure failures",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"log_level must be one of {valid}, got '{v}'")
        return upper


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get application settings (cached singleton).

    Raises ValidationError at startup if required env vars are missing.
    """
    return Settings()
