"""
Structured logging package.

Provides JSON-formatted logging with automatic request_id injection.
Use ``get_logger(__name__)`` instead of ``logging.getLogger(__name__)``
throughout the application.
"""

from app.core.logging.config import configure_logging, get_logger

__all__ = [
    "configure_logging",
    "get_logger",
]
