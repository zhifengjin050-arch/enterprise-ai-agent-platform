"""Knowledge Agent package.

Provides the conversational knowledge Q&A capability:
- Intent recognition
- Query rewriting
- Context building
- LLM answer generation
- Citation tracking

This is a single-agent implementation following a clear pipeline,
not a multi-agent orchestration framework.
"""

from app.agent.answer_generator import AnswerGenerator
from app.agent.knowledge_agent import KnowledgeAgent, KnowledgeAgentResult

__all__ = [
    "KnowledgeAgent",
    "KnowledgeAgentResult",
    "AnswerGenerator",
]
