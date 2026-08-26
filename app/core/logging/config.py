"""
Structured logging configuration.

Provides a JSON-based structured logging format suitable for
production log aggregation (ELK, Loki, CloudWatch, etc.).

Usage:
    from app.core.logging import configure_logging, get_logger

    configure_logging()
    logger = get_logger(__name__)
    logger.info("Service started", extra={"version": "1.0"})
"""

from __future__ import annotations

import logging
import sys

from app.core.logging.formatter import StructuredFormatter


def configure_logging(
    level: str = "INFO",
    json_format: bool = True,
) -> None:
    """Configure the root logger with structured output.

    Args:
        level: Logging level name (DEBUG, INFO, WARNING, ERROR).
        json_format: If True, use JSON-formatted output.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates during reconfiguration
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if json_format:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given module name.

    Use this instead of ``logging.getLogger(__name__)`` to ensure
    consistent structured logging across the application.

    Args:
        name: Usually ``__name__`` from the calling module.

    Returns:
        A configured Logger instance.
    """
    return logging.getLogger(name)
