"""Workflow package - LangGraph-powered knowledge processing pipelines.

Replaces the old agent/ module. LangGraph is used as a Knowledge Workflow
Engine, not a conversational agent. It orchestrates document processing
and incident analysis flows.

Public API:
    KnowledgeState          — State schema (no chat/question fields)
    knowledge_pipeline      — Compiled LangGraph pipeline (or fallback)
    WorkflowOrchestrator    — Execution, resume, approve/reject manager
    orchestrator            — Singleton orchestrator instance
    WorkflowRun             — ORM model for persisted runs
"""
from app.workflow.knowledge_pipeline import knowledge_pipeline
from app.workflow.models import WorkflowRun
from app.workflow.orchestrator import WorkflowOrchestrator, orchestrator
from app.workflow.state import KnowledgeState

__all__ = [
    "KnowledgeState",
    "knowledge_pipeline",
    "WorkflowOrchestrator",
    "orchestrator",
    "WorkflowRun",
]
