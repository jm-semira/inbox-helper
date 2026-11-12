"""Application configuration management with environment variable support."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

from inbox_helper.core.exceptions import ConfigurationError

# Load variables from .env file if present
load_dotenv()

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
AppEnv = Literal["development", "testing", "production"]
ProviderType = Literal["mock", "ollama", "openai", "gemini"]


@dataclass(frozen=True)
class AppConfig:
    """Immutable application-wide configuration."""

    env: AppEnv = "development"
    db_path: str = "data/inbox_helper.db"
    log_level: LogLevel = "INFO"
    llm_provider: ProviderType = "mock"
    llm_model: str = "mock-model-v1"
    llm_timeout: float = 30.0
    llm_temperature: float = 0.2
    openai_api_key: str | None = field(default=None, repr=False)
    gemini_api_key: str | None = field(default=None, repr=False)
    ollama_base_url: str = "http://localhost:11434"

    def __post_init__(self) -> None:
        if not math.isfinite(self.llm_timeout) or not 0 < self.llm_timeout <= 300:
            raise ConfigurationError(
                "llm_timeout must be finite and between 0 and 300 seconds."
            )

    @classmethod
    def from_env(cls) -> AppConfig:
        """Create configuration loaded from environment variables."""
        env = os.getenv("INBOX_HELPER_ENV", "development").lower()
        if env not in ("development", "testing", "production"):
            raise ConfigurationError(
                f"Invalid INBOX_HELPER_ENV: '{env}'. Must be one of: development, testing, production"
            )

        log_level = os.getenv("INBOX_HELPER_LOG_LEVEL", "INFO").upper()
        if log_level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ConfigurationError(
                f"Invalid INBOX_HELPER_LOG_LEVEL: '{log_level}'"
            )

        provider = os.getenv("INBOX_HELPER_LLM_PROVIDER", "mock").lower()
        if provider not in ("mock", "ollama", "openai", "gemini"):
            raise ConfigurationError(
                f"Invalid INBOX_HELPER_LLM_PROVIDER: '{provider}'. Must be one of: mock, ollama, openai, gemini"
            )

        raw_timeout = os.getenv("INBOX_HELPER_LLM_TIMEOUT", "30.0")
        try:
            llm_timeout = float(raw_timeout)
            if not math.isfinite(llm_timeout) or not 0 < llm_timeout <= 300:
                raise ValueError
        except ValueError:
            raise ConfigurationError(
                "INBOX_HELPER_LLM_TIMEOUT must be finite and between 0 and "
                f"300 seconds, got '{raw_timeout}'"
            )

        raw_temp = os.getenv("INBOX_HELPER_LLM_TEMPERATURE", "0.2")
        try:
            llm_temperature = float(raw_temp)
            if not 0.0 <= llm_temperature <= 2.0:
                raise ValueError
        except ValueError:
            raise ConfigurationError(
                f"INBOX_HELPER_LLM_TEMPERATURE must be between 0.0 and 2.0, got '{raw_temp}'"
            )

        return cls(
            env=env,  # type: ignore[arg-type]
            db_path=os.getenv("INBOX_HELPER_DB_PATH", "data/inbox_helper.db"),
            log_level=log_level,  # type: ignore[arg-type]
            llm_provider=provider,  # type: ignore[arg-type]
            llm_model=os.getenv("INBOX_HELPER_LLM_MODEL", "mock-model-v1"),
            llm_timeout=llm_timeout,
            llm_temperature=llm_temperature,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )

    def ensure_db_directory(self) -> None:
        """Ensure the parent directory for the database file exists."""
        if self.db_path != ":memory:":
            db_file = Path(self.db_path)
            db_file.parent.mkdir(parents=True, exist_ok=True)


# Global configuration instance accessor
_current_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Retrieve or initialize the active application configuration."""
    global _current_config
    if _current_config is None:
        _current_config = AppConfig.from_env()
    return _current_config


def set_config(config: AppConfig | None) -> None:
    """Override application configuration (primarily for testing)."""
    global _current_config
    _current_config = config
