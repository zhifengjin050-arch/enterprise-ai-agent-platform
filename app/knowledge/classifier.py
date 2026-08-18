"""
Knowledge classification engine.

Two-layer classification strategy:
1. Rule-based classifier (keyword matching, fast)
2. LLM classifier fallback (when rule confidence < 0.8)

Output: DocumentClassification(doc_type, confidence, reason)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from app.knowledge.models import KnowledgeDocument
from app.llm.cache import cached_call, store_cached_result
from app.prompts.classification import (
    CLASSIFICATION_SCHEMA,
    CLASSIFICATION_SYSTEM_PROMPT,
    build_classification_prompt,
)

CLASSIFICATION_RULES: Dict[str, List[str]] = {
    "SOP": [
        "standard operating procedure",
        "sop",
        "procedure",
        "steps",
        "step-by-step",
        "troubleshooting",
        "故障处理",
        "排查步骤",
        "操作流程",
        "处理流程",
    ],
    "INCIDENT": [
        "incident",
        "postmortem",
        "root cause",
        "故障报告",
        "事故分析",
        "故障复盘",
        "原因分析",
        "影响范围",
    ],
    "BEST_PRACTICE": [
        "best practice",
        "best practices",
        "recommendation",
        "guideline",
        "最佳实践",
        "推荐方案",
        "规范指南",
    ],
    "ARCHITECTURE": [
        "architecture",
        "system design",
        "architecture overview",
        "架构设计",
        "系统架构",
        "技术架构",
        "设计方案",
    ],
    "CONFIGURATION": [
        "configuration",
        "config",
        "setup guide",
        "installation",
        "配置指南",
        "安装部署",
        "参数配置",
        "部署规范",
    ],
}


@dataclass
class DocumentClassification:
    """Result of document classification.

    Attributes:
        doc_type: The classified document type string.
        confidence: Confidence score (0.0 to 1.0).
        reason: Explanation of the classification decision.
    """

    doc_type: str
    confidence: float = 0.0
    reason: str = ""


def rule_classifier(title: str, content: str) -> DocumentClassification:
    """First-layer rule-based classification using keyword matching.

    Args:
        title: Document title.
        content: Document markdown content.

    Returns:
        DocumentClassification with doc_type, computed confidence, and reason.
    """
    text = f"{title} {content}".lower()
    scores: Dict[str, int] = {}
    matched_keywords: Dict[str, List[str]] = {}

    for doc_type, keywords in CLASSIFICATION_RULES.items():
        matched = [kw for kw in keywords if kw.lower() in text]
        score = len(matched)
        if score > 0:
            scores[doc_type] = score
            matched_keywords[doc_type] = matched

    if not scores:
        return DocumentClassification(
            doc_type="other",
            confidence=0.3,
            reason="No rule-based keywords matched. Low confidence.",
        )

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    # Convert raw score to a normalized confidence (0.0-1.0)
    # If >= 2 keywords match → confident classification
    # If only 1 keyword matches → moderate confidence
    if best_score >= 2:
        confidence = 0.85
    elif best_score == 1:
        confidence = 0.6
    else:
        confidence = 0.3
    confidence = round(min(1.0, max(0.3, confidence)), 2)

    matched_list = matched_keywords.get(best_type, [])
    reason = (
        f"Rule matched {best_score} keyword(s): {', '.join(matched_list[:5])}"
        if matched_list
        else f"Rule matched {best_score} keyword(s)"
    )

    return DocumentClassification(
        doc_type=best_type.lower(),
        confidence=confidence,
        reason=reason,
    )


class LLMClassifier:
    """Second-layer LLM-based classifier.

    Used when rule classifier confidence < 0.8.
    Leverages structured_output for JSON Schema-compliant results.
    Results are cached based on document content hash.
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

    async def classify(
        self,
        title: str,
        content: str,
        use_cache: bool = True,
    ) -> DocumentClassification:
        """Classify document using LLM with structured output.

        Args:
            title: Document title.
            content: Document markdown content.
            use_cache: Whether to check cache first.

        Returns:
            DocumentClassification with doc_type, confidence, reason.
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
                return DocumentClassification(
                    doc_type=cached_value.get("doc_type", "other"),
                    confidence=cached_value.get("confidence", 0.0),
                    reason=cached_value.get("reason", "Cached result"),
                )

        # Build prompt
        prompt = build_classification_prompt(title, content)

        try:
            result = await self._llm.structured_output(
                prompt=prompt,
                schema=CLASSIFICATION_SCHEMA,
                system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
                temperature=0.1,
            )

            doc_type = result.get("doc_type", "other")
            confidence = min(1.0, max(0.0, float(result.get("confidence", 0.0))))
            reason = result.get("reason", "LLM classification")

            classification = DocumentClassification(
                doc_type=doc_type,
                confidence=confidence,
                reason=reason,
            )

            # Cache result
            if use_cache:
                store_cached_result(
                    prompt="",
                    result={
                        "doc_type": doc_type,
                        "confidence": confidence,
                        "reason": reason,
                    },
                    use_content_hash=True,
                    content=content,
                    content_title=title,
                )

            return classification

        except (ValueError, ConnectionError) as e:
            return DocumentClassification(
                doc_type="other",
                confidence=0.0,
                reason=f"LLM classification failed: {e}",
            )


async def classify_document(
    document: KnowledgeDocument,
    use_llm_fallback: bool = True,
    llm_client=None,
) -> DocumentClassification:
    """Two-layer document classification.

    Strategy:
        1. Run rule classifier first.
        2. If rule confidence < 0.8, fall back to LLM classifier.

    Args:
        document: KnowledgeDocument to classify.
        use_llm_fallback: Whether to use LLM fallback when rule confidence is low.
        llm_client: Optional LLM client override for testing.

    Returns:
        DocumentClassification with doc_type, confidence, reason.
    """
    title = document.title or ""
    content = document.content or ""

    # Layer 1: Rule-based
    rule_result = rule_classifier(title, content)

    # If rule has high confidence, use it directly
    if rule_result.confidence >= 0.8:
        return rule_result

    # Layer 2: LLM Fallback
    if use_llm_fallback:
        llm_classifier = LLMClassifier(llm_client=llm_client)
        llm_result = await llm_classifier.classify(title, content)

        # Use LLM result if its confidence is higher than rule
        if llm_result.confidence > rule_result.confidence:
            return llm_result

    return rule_result


def batch_classify(
    documents: List[KnowledgeDocument],
    use_llm_fallback: bool = True,
) -> Dict[str, DocumentClassification]:
    """Classify multiple documents at once.

    Note: For batch classification with LLM fallback, this function
    processes documents sequentially due to LLM API calls.

    Args:
        documents: List of documents to classify.
        use_llm_fallback: Whether to use LLM fallback.

    Returns:
        Dict mapping document IDs to DocumentClassification results.
    """
    import asyncio

    async def _batch():
        results = {}
        for doc in documents:
            if doc.id:
                results[str(doc.id)] = await classify_document(
                    doc,
                    use_llm_fallback=use_llm_fallback,
                )
        return results

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_batch())

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _batch()).result()
