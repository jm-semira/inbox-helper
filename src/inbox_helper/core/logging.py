"""Structured application logging configuration with secret redaction."""

from __future__ import annotations

import logging
import re
import sys
from typing import ClassVar


class SensitiveDataFilter(logging.Filter):
    """Logging filter that scrubs suspected API keys, tokens, and secrets."""

    PATTERNS: ClassVar[list[tuple[re.Pattern[str], str]]] = [
        (
            re.compile(
                r"((?:api[_-]?key|secret|token|password)[\"']?\s*[:=]\s*[\"']?)([^\"'\s,]+)",
                re.IGNORECASE,
            ),
            r"\1[REDACTED]",
        ),
        (
            re.compile(r"(\bBearer\s+)[A-Za-z0-9._~+/-]+=*", re.IGNORECASE),
            r"\1[REDACTED]",
        ),
        (re.compile(r"\bsk-[a-zA-Z0-9]{20,}\b", re.IGNORECASE), "[REDACTED]"),
        (re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "[REDACTED]"),
        (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"), "[REDACTED]"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self.redact(record.getMessage())
        record.args = ()
        return True

    @classmethod
    def redact(cls, text: str) -> str:
        scrubbed = text
        for pattern, replacement in cls.PATTERNS:
            scrubbed = pattern.sub(replacement, scrubbed)
        return scrubbed


def configure_logging(level: str = "INFO", stream: object = None) -> logging.Logger:
    """Configure structured logging for Inbox Helper.

    Args:
        level: Minimum log level string (e.g. 'DEBUG', 'INFO').
        stream: Target stream for log output (defaults to sys.stderr).

    Returns:
        The root or primary inbox_helper logger.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger = logging.getLogger("inbox_helper")
    logger.setLevel(numeric_level)

    # Avoid duplicate handlers if reconfigured
    if not logger.handlers:
        handler = logging.StreamHandler(stream or sys.stderr)
        handler.setLevel(numeric_level)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter())
        logger.addHandler(handler)
    else:
        for handler in logger.handlers:
            handler.setLevel(numeric_level)
            if not any(
                isinstance(log_filter, SensitiveDataFilter)
                for log_filter in handler.filters
            ):
                handler.addFilter(SensitiveDataFilter())

    return logger


def get_logger(name: str) -> logging.Logger:
    """Obtain a child logger under the 'inbox_helper' namespace."""
    return logging.getLogger(f"inbox_helper.{name}")
