"""Interfaces for application dependencies."""

from inbox_helper.application.ports.email_repository import EmailRepository
from inbox_helper.application.ports.email_csv_source import EmailCsvSource
from inbox_helper.application.ports.llm_provider import LLMProvider

__all__ = ["EmailRepository", "EmailCsvSource", "LLMProvider"]
