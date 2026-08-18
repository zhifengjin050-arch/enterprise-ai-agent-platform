"""DB-backed Prompt Management (Phase 6).

Coexists with static prompt modules under ``app.prompts``.
"""

from app.prompt.manager import PromptManager
from app.prompt.models import PromptTemplate

__all__ = ["PromptTemplate", "PromptManager"]
