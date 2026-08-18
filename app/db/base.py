"""
SQLAlchemy declarative base.

All ORM models inherit from Base. Alembic uses Base.metadata for migrations.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass
