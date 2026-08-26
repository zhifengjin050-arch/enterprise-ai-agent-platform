"""AI-powered knowledge quality analyzer.

Provides two-layer quality analysis:
1. Rule-based heuristic analyzer (fast, offline)
2. LLM quality analyzer (deep, structured analysis)

Scoring dimensions (LLM):
- Structural Integrity (30%)
- Technical Accuracy (30%)
- Executability (25%)
- Timeliness (15%)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.knowledge.models import DocumentStatus, KnowledgeDocument
from app.llm.cache import cached_call, store_cached_result
from app.prompts.quality_review import (
    QUALITY_SCHEMA,
    QUALITY_SYSTEM_PROMPT,
    build_quality_prompt,
)


@dataclass
class QualityResult:
    """Result of quality analysis.

    Attributes:
        score: Overall quality score (0.0 to 1.0).
        issues: List of specific issues found.
        suggestions: List of improvement suggestions.
        dimension_scores: Individual dimension scores.
    """

    score: float = 0.0
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    dimension_scores: Dict[str, float] = field(default_factory=dict)


# ──────────────────────────────────────────────
# Rule-based heuristic analyzer
# ──────────────────────────────────────────────


def rule_quality_analyzer(title: str, content: str) -> QualityResult:
    """First-layer rule-based quality analysis.

    Evaluates completeness, structure, and validity heuristically.

    Args:
        title: Document title.
        content: Document markdown content.

    Returns:
        QualityResult with score and issues.
    """
    issues: List[str] = []
    suggestions: List[str] = []

    # ── Completeness (40% heuristic) ──
    length = len(content.strip())
    if length < 50:
        completeness = 0.0
        issues.append("Content too short (<50 chars)")
    elif length < 200:
        completeness = 0.3
        issues.append("Content is brief (<200 chars)")
    elif length < 1000:
        completeness = 0.7
    elif length < 5000:
        completeness = 0.9
    else:
        completeness = 1.0

    if not title or title == "Untitled":
        completeness = max(0.0, completeness - 0.2)
        issues.append("Missing descriptive title")

    # ── Structure (30% heuristic) ──
    heading_count = content.count("# ")
    if heading_count >= 3:
        structure = 1.0
    elif heading_count >= 1:
        structure = 0.6
    else:
        structure = 0.2
        issues.append("No markdown headings found")

    if "```" in content or "- " in content:
        structure = min(1.0, structure + 0.2)

    # ── Validity (30% heuristic) ──
    if length < 20:
        validity = 0.0
        issues.append("Content appears empty or placeholder")
    elif any(marker in content for marker in ["todo", "TODO", "coming soon", "TBD"]):
        validity = 0.3
        issues.append("Content contains placeholder markers (TODO/TBD)")
    else:
        validity = 0.9

    # ── Overall score (weighted) ──
    score = completeness * 0.4 + structure * 0.3 + validity * 0.3
    score = round(max(0.0, min(1.0, score)), 2)

    return QualityResult(
        score=score,
        issues=issues,
        suggestions=suggestions,
        dimension_scores={
            "completeness": round(completeness, 2),
            "structure": round(structure, 2),
            "validity": round(validity, 2),
        },
    )


# ──────────────────────────────────────────────
# LLM Quality Analyzer
# ──────────────────────────────────────────────


class LLMQualityAnalyzer:
    """Second-layer LLM-based quality analyzer.

    Uses structured output to score documents across four dimensions:
    - Structural Integrity (30%)
    - Technical Accuracy (30%)
    - Executability (25%)
    - Timeliness (15%)

    Results are cached based on document content hash to avoid redundant calls.
    """

    def __init__(self, llm_client=None):
        """Initialize with optional LLM client override for testing.

        Args:
            llm_client: LLM service instance. Defaults to global llm_client.
        """
        if llm_client is not None:
            self._llm = llm_client
        else:
            from app.llm.client import llm_client as _llm

            self._llm = _llm

    async def analyze(
        self,
        title: str,
        content: str,
        use_cache: bool = True,
    ) -> QualityResult:
        """Analyze document quality using LLM with structured output.

        Args:
            title: Document title.
            content: Document markdown content.
            use_cache: Whether to check cache first.

        Returns:
            QualityResult with score, issues, suggestions, dimension_scores.
        """
        # Check cache
        if use_cache:
            cached_value, hit = cached_call(
                prompt="",
                use_content_hash=True,
                content=content,
                content_title=title,
            )
            if hit and isinstance(cached_value, dict):
                return self._dict_to_quality_result(cached_value)

        # Build prompt
        prompt = build_quality_prompt(title, content)

        try:
            result = await self._llm.structured_output(
                prompt=prompt,
                schema=QUALITY_SCHEMA,
                system_prompt=QUALITY_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=4096,
            )

            quality = QualityResult(
                score=min(1.0, max(0.0, float(result.get("score", 0.0)))),
                issues=result.get("issues", []),
                suggestions=result.get("suggestions", []),
                dimension_scores={
                    "structural_integrity": min(
                        1.0,
                        max(0.0, float(result.get("structural_integrity", 0.0))),
                    ),
                    "technical_accuracy": min(
                        1.0,
                        max(0.0, float(result.get("technical_accuracy", 0.0))),
                    ),
                    "executability": min(
                        1.0,
                        max(0.0, float(result.get("executability", 0.0))),
                    ),
                    "timeliness": min(
                        1.0,
                        max(0.0, float(result.get("timeliness", 0.0))),
                    ),
                },
            )

            # Cache result
            if use_cache:
                store_cached_result(
                    prompt="",
                    result={
                        "score": quality.score,
                        "issues": quality.issues,
                        "suggestions": quality.suggestions,
                        "structural_integrity": quality.dimension_scores.get(
                            "structural_integrity", 0.0
                        ),
                        "technical_accuracy": quality.dimension_scores.get(
                            "technical_accuracy", 0.0
                        ),
                        "executability": quality.dimension_scores.get("executability", 0.0),
                        "timeliness": quality.dimension_scores.get("timeliness", 0.0),
                    },
                    use_content_hash=True,
                    content=content,
                    content_title=title,
                )

            return quality

        except (ValueError, ConnectionError) as e:
            return QualityResult(
                score=0.0,
                issues=[f"LLM quality analysis failed: {e}"],
                suggestions=["Retry or check LLM configuration."],
            )

    def _dict_to_quality_result(self, data: Dict) -> QualityResult:
        """Convert a dictionary to QualityResult.

        Args:
            data: Dictionary containing quality data.

        Returns:
            QualityResult instance.
        """
        return QualityResult(
            score=min(1.0, max(0.0, float(data.get("score", 0.0)))),
            issues=data.get("issues", []),
            suggestions=data.get("suggestions", []),
            dimension_scores={
                "structural_integrity": min(
                    1.0,
                    max(0.0, float(data.get("structural_integrity", 0.0))),
                ),
                "technical_accuracy": min(
                    1.0,
                    max(0.0, float(data.get("technical_accuracy", 0.0))),
                ),
                "executability": min(
                    1.0,
                    max(0.0, float(data.get("executability", 0.0))),
                ),
                "timeliness": min(
                    1.0,
                    max(0.0, float(data.get("timeliness", 0.0))),
                ),
            },
        )


# ──────────────────────────────────────────────
# Two-layer quality analysis entry point
# ──────────────────────────────────────────────


async def analyze_document_quality(
    document: KnowledgeDocument,
    use_llm_fallback: bool = True,
    llm_client=None,
) -> QualityResult:
    """Two-layer document quality analysis.

    Strategy:
        1. Run rule-based heuristic analyzer first.
        2. If rule score < 0.8, fall back to LLM Quality Analyzer.

    Args:
        document: KnowledgeDocument to analyze.
        use_llm_fallback: Whether to use LLM fallback.
        llm_client: Optional LLM client override for testing.

    Returns:
        QualityResult with score, issues, suggestions.
    """
    title = document.title or ""
    content = document.content or ""

    # Layer 1: Rule-based
    rule_result = rule_quality_analyzer(title, content)

    # If rule has high score, use it directly
    if rule_result.score >= 0.8:
        return rule_result

    # Layer 2: LLM Fallback
    if use_llm_fallback:
        llm_analyzer = LLMQualityAnalyzer(llm_client=llm_client)
        llm_result = await llm_analyzer.analyze(title, content)

        # Use LLM result if it provides deeper analysis
        if llm_result.score > rule_result.score or len(llm_result.issues) > len(rule_result.issues):
            return llm_result

    return rule_result


# ──────────────────────────────────────────────
# Existing document quality report functionality (backward compat)
# ──────────────────────────────────────────────


@dataclass
class DocumentQualityReport:
    """Quality report for a single document."""

    document_id: int
    title: str
    completeness_score: float
    freshness_score: float
    is_expired: bool
    missing_sections: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    duplicate_of: Optional[int] = None
    duplicate_score: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "title": self.title,
            "completeness_score": self.completeness_score,
            "freshness_score": self.freshness_score,
            "is_expired": self.is_expired,
            "missing_sections": self.missing_sections,
            "suggestions": self.suggestions,
            "duplicate_of": self.duplicate_of,
            "duplicate_score": self.duplicate_score,
        }


@dataclass
class KnowledgeBaseHealthReport:
    """Overall health report for the entire knowledge base."""

    total_documents: int
    active_documents: int
    expired_documents: int
    avg_completeness: float
    avg_freshness: float
    duplicate_count: int
    documents: List[DocumentQualityReport] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_documents": self.total_documents,
            "active_documents": self.active_documents,
            "expired_documents": self.expired_documents,
            "avg_completeness": round(self.avg_completeness, 2),
            "avg_freshness": round(self.avg_freshness, 2),
            "duplicate_count": self.duplicate_count,
            "documents": [d.to_dict() for d in self.documents],
            "recommendations": self.recommendations,
        }


async def legacy_analyze_document_quality(
    session: AsyncSession,
    document: KnowledgeDocument,
) -> DocumentQualityReport:
    """Legacy document quality analysis (backward compatibility).

    Args:
        session: Database session.
        document: The document to analyze.

    Returns:
        DocumentQualityReport with scores.
    """
    now = datetime.utcnow()

    days_since_update = (now - document.updated_at).days if document.updated_at else 999
    freshness_rules = {
        "sop": 180,
        "config": 90,
        "architecture": 365,
        "best_practice": 180,
        "incident": 365,
        "general": 365,
    }
    max_age_days = freshness_rules.get(document.doc_type, 365)
    freshness_score = max(0.0, 1.0 - (days_since_update / max_age_days))

    is_expired = document.is_expired or (document.expires_at and document.expires_at < now)

    missing_sections = []
    suggestions_list = []
    completeness_score = 0.7

    if document.content and len(document.content.strip()) > 50:
        ai_prompt = f"""分析以下文档的完整性，识别缺失的关键部分。

文档标题: {document.title}
文档类型: {document.doc_type}
文档内容:
{document.content[:3000]}...

请分析：
1. 完整性评分 (0-1)
2. 哪些关键部分可能缺失
3. 改进建议

输出格式：
评分: [0-1]
缺失: [部分1, 部分2]
建议: [建议1, 建议2]
"""
        from app.llm.client import llm_client

        ai_response = await llm_client.chat(ai_prompt)
        completeness_score = _extract_score(ai_response)
        missing_sections = _extract_missing(ai_response)
        suggestions_list = _extract_suggestions(ai_response)

    return DocumentQualityReport(
        document_id=document.id,
        title=document.title,
        completeness_score=completeness_score,
        freshness_score=freshness_score,
        is_expired=is_expired,
        missing_sections=missing_sections,
        suggestions=suggestions_list,
    )


async def detect_duplicates(
    session: AsyncSession,
    document: KnowledgeDocument,
    threshold: float = 0.8,
) -> Optional[Tuple[int, float]]:
    """Detect if a document has duplicates.

    Uses basic content overlap analysis.
    TODO: Replace with proper embedding-based similarity.

    Args:
        session: Database session.
        document: The document to check.
        threshold: Similarity threshold.

    Returns:
        Tuple of (duplicate_document_id, similarity_score) or None.
    """
    result = await session.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id != document.id,
            KnowledgeDocument.status != DocumentStatus.ARCHIVED,
        )
    )
    others = list(result.scalars().all())

    doc_words = set(document.content.lower().split())
    if not doc_words:
        return None

    best_match = None
    best_score = 0.0

    for other in others:
        other_words = set(other.content.lower().split())
        if not other_words:
            continue

        intersection = doc_words & other_words
        union = doc_words | other_words
        jaccard = len(intersection) / len(union) if union else 0

        if jaccard > best_score:
            best_score = jaccard
            best_match = other.id

    if best_score >= threshold:
        return (best_match, best_score)
    return None


async def generate_health_report(
    session: AsyncSession,
) -> KnowledgeBaseHealthReport:
    """Generate a comprehensive health report for the knowledge base.

    Args:
        session: Database session.

    Returns:
        KnowledgeBaseHealthReport with overall stats and per-document analysis.
    """
    result = await session.execute(
        select(KnowledgeDocument).options(
            selectinload(KnowledgeDocument.categories),
            selectinload(KnowledgeDocument.tags),
        )
    )
    documents = list(result.scalars().all())

    active_docs = [d for d in documents if d.is_active]
    expired_docs = [
        d
        for d in documents
        if d.expires_at and d.expires_at.replace(tzinfo=None) < datetime.utcnow()
    ]

    reports = []
    total_completeness = 0.0
    total_freshness = 0.0
    duplicate_count = 0

    for doc in documents[:50]:
        quality = await legacy_analyze_document_quality(session, doc)
        reports.append(quality)
        total_completeness += quality.completeness_score
        total_freshness += quality.freshness_score

        dup = await detect_duplicates(session, doc)
        if dup:
            duplicate_count += 1
            quality.duplicate_of = dup[0]
            quality.duplicate_score = dup[1]

    n = len(documents) if documents else 1
    avg_completeness = total_completeness / n
    avg_freshness = total_freshness / n

    recommendations = []
    if avg_completeness < 0.6:
        recommendations.append("知识库整体完整度较低，建议补充关键文档的缺失部分")
    if avg_freshness < 0.5:
        recommendations.append("大量文档可能已过期，建议安排定期审查和更新")
    if duplicate_count > 0:
        recommendations.append(f"检测到 {duplicate_count} 个可能的重复文档，建议合并或清理")
    if expired_docs:
        recommendations.append(f"有 {len(expired_docs)} 个文档已过期，建议审查")
    if not documents:
        recommendations.append("知识库为空，请导入文档")

    return KnowledgeBaseHealthReport(
        total_documents=len(documents),
        active_documents=len(active_docs),
        expired_documents=len(expired_docs),
        avg_completeness=avg_completeness,
        avg_freshness=avg_freshness,
        duplicate_count=duplicate_count,
        documents=reports,
        recommendations=recommendations,
    )


def _extract_score(ai_response: str) -> float:
    """Extract completeness score from AI response."""
    match = re.search(r"评分:\s*([0-9.]+)", ai_response)
    if match:
        try:
            score = float(match.group(1))
            return max(0.0, min(1.0, score))
        except ValueError:
            pass
    return 0.7


def _extract_missing(ai_response: str) -> List[str]:
    """Extract missing sections from AI response."""
    missing = []
    match = re.search(r"缺失:\s*(.+?)(?:\n|$)", ai_response)
    if match:
        items = match.group(1).strip()
        missing = [
            item.strip().lstrip("- ").lstrip("* ").strip("[] ")
            for item in items.split(",")
            if item.strip()
        ]
    return missing


def _extract_suggestions(ai_response: str) -> List[str]:
    """Extract improvement suggestions from AI response."""
    suggestions = []
    match = re.search(r"建议:\s*(.+?)(?:\n\n|$)", ai_response, re.DOTALL)
    if match:
        text = match.group(1).strip()
        suggestions = [
            line.strip().lstrip("- ").lstrip("* ").lstrip("1234567890. ")
            for line in text.split("\n")
            if line.strip()
        ]
    return suggestions
