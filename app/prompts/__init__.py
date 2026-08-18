"""
Prompt management package.

Centralizes all LLM prompts for classification, tag generation,
quality review, and answer generation to avoid hardcoding
prompts in business logic.
"""

from app.prompts.answer_generation import (
    ANSWER_SCHEMA,
    ANSWER_SYSTEM_PROMPT,
    build_answer_prompt,
)
from app.prompts.classification import (
    CLASSIFICATION_SCHEMA,
    CLASSIFICATION_SYSTEM_PROMPT,
    build_classification_prompt,
)
from app.prompts.quality_review import (
    QUALITY_SCHEMA,
    QUALITY_SYSTEM_PROMPT,
    build_quality_prompt,
)
from app.prompts.tag_generation import (
    TAG_GENERATION_SCHEMA,
    TAG_GENERATION_SYSTEM_PROMPT,
    build_tag_generation_prompt,
)

__all__ = [
    "CLASSIFICATION_SYSTEM_PROMPT",
    "CLASSIFICATION_SCHEMA",
    "build_classification_prompt",
    "TAG_GENERATION_SYSTEM_PROMPT",
    "TAG_GENERATION_SCHEMA",
    "build_tag_generation_prompt",
    "QUALITY_SYSTEM_PROMPT",
    "QUALITY_SCHEMA",
    "build_quality_prompt",
    "ANSWER_SYSTEM_PROMPT",
    "ANSWER_SCHEMA",
    "build_answer_prompt",
]
