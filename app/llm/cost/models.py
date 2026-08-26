"""LLM Cost ORM model and request type enum.

Tracks each LLM API call with token counts and estimated cost.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RequestType(str, enum.Enum):
    """Type of LLM request for cost attribution."""

    CLASSIFICATION = "classification"
    TAGGING = "tagging"
    QUALITY = "quality"
    ANSWER_GENERATION = "answer_generation"
    INTENT = "intent"
    QUERY_REWRITE = "query_rewrite"
    ENTITY_EXTRACTION = "entity_extraction"
    RELATION_EXTRACTION = "relation_extraction"
    OTHER = "other"


class LLMCostRecord(Base):
    """Record of a single LLM API call for cost tracking.

    Attributes:
        id: UUID primary key.
        provider: LLM provider name (e.g., "deepseek", "openai").
        model: Model identifier (e.g., "deepseek-chat", "gpt-4").
        request_type: Categorization of the API call purpose.
        prompt_tokens: Number of input tokens.
        completion_tokens: Number of output tokens.
        total_tokens: Total tokens used.
        estimated_cost: Estimated USD cost of the call.
        created_at: Timestamp of the API call.
    """

    __tablename__ = "llm_cost_records"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="unknown")
    request_type: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<LLMCostRecord id={self.id} "
            f"model={self.model} type={self.request_type} "
            f"tokens={self.total_tokens} cost=${self.estimated_cost:.6f}>"
        )
