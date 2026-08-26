"""Knowledge workflow state definition.

Defines the state schema for LangGraph-based knowledge processing pipeline.
This is NOT a conversational Agent state — no question/answer/chat fields.

Status lifecycle:
    pending -> processing -> (review -> processing) -> completed / failed
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class KnowledgeState(TypedDict, total=False):
    """State for the enterprise knowledge processing pipeline.

    Each field maps to a specific stage of the pipeline.
    Fields are intentionally kept clean — no chat history, no conversation.
    """

    # --- Identity ---
    document_id: str
    file_path: Optional[str]
    workflow_run_id: Optional[str]

    # --- Content ---
    raw_content: Optional[str]
    markdown_content: Optional[str]
    title: Optional[str]

    # --- Classification & Tagging ---
    doc_type: Optional[
        str
    ]  # sop | incident | architecture | configuration | best_practice | manual
    tags: List[str]

    # --- Quality ---
    quality_score: float
    quality_issues: List[str]

    # --- Embedding ---
    embedding_id: Optional[str]

    # --- Persistence ---
    stored: bool
    indexed: bool

    # --- Entity & Relation (Knowledge Graph Lite) ---
    entities: List[Dict[str, Any]]
    relations: List[Dict[str, Any]]

    # --- Review ---
    need_review: bool
    review_decision: Optional[str]  # approved | rejected
    review_comment: Optional[str]

    # --- Workflow Control ---
    status: str  # pending | processing | review | completed | failed
    current_node: Optional[str]
    error: Optional[str]
    metadata: Dict[str, Any]
