"""Query understanding package.

Handles intent classification, query rewriting, and context building
for the conversational knowledge agent.
"""
from app.query.builder import ContextBuilder, build_llm_context
from app.query.intent import QueryIntent, classify_intent
from app.query.rewrite import QueryRewriteService, rewrite_query

__all__ = [
    "QueryIntent",
    "classify_intent",
    "QueryRewriteService",
    "rewrite_query",
    "ContextBuilder",
    "build_llm_context",
]
