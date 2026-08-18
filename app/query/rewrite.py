"""Query rewriting service.

Generates multiple query variants from a user's natural language query,
enabling broader document retrieval across different phrasings.

Two-layer strategy:
1. Rule-based synonym expansion (fast)
2. LLM fallback for deeper query understanding
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List

logger = logging.getLogger(__name__)


# ── Synonym expansion rules ────────────────────────────

QUERY_REWRITE_RULES: Dict[str, List[str]] = {
    "502": ["502 bad gateway", "bad gateway error", "网关错误"],
    "503": ["503 service unavailable", "service unavailable", "服务不可用"],
    "504": ["504 gateway timeout", "gateway timeout", "网关超时"],
    "nginx": ["nginx error", "nginx configuration", "nginx troubleshooting"],
    "redis": ["redis error", "redis connection", "redis unavailable"],
    "kubernetes": ["k8s", "kubernetes cluster", "kubectl"],
    "k8s": ["kubernetes", "k8s cluster", "kubectl"],
    "docker": ["docker container", "docker engine", "docker daemon"],
    "pod": ["kubernetes pod", "k8s pod", "pod status"],
    "crashloopbackoff": [
        "CrashLoopBackOff", "pod crash loop", "container crash looping",
    ],
    "宕机": ["outage", "downtime", "service down", "不可用"],
    "故障": ["incident", "fault", "error", "异常"],
    "监控": ["monitoring", "alert", "告警", "prometheus", "grafana"],
}

# Intent-specific rewrite templates
INTENT_TEMPLATES: Dict[str, List[str]] = {
    "incident_analysis": [
        "{query} 故障原因",
        "{query} 解决方案",
        "{query} troubleshooting",
        "{query} 恢复步骤",
    ],
    "sop_lookup": [
        "{query} 操作步骤",
        "{query} 操作流程",
        "{query} how to",
        "{query} step by step",
    ],
    "configuration_help": [
        "{query} 配置指南",
        "{query} 配置参数",
        "{query} configuration",
        "{query} setup guide",
    ],
    "architecture_question": [
        "{query} 架构设计",
        "{query} 系统架构",
        "{query} architecture design",
    ],
}


@dataclass
class RewriteResult:
    """Result of query rewriting.

    Attributes:
        original_query: The original user query.
        rewritten_queries: List of rewritten query variants.
    """
    original_query: str = ""
    rewritten_queries: List[str] = field(default_factory=list)


def _rule_rewrite(query: str, intent: str) -> List[str]:
    """First-layer rule-based query rewriting.

    Args:
        query: Original user query.
        intent: Recognized intent for template selection.

    Returns:
        List of rewritten query variants.
    """
    query_lower = query.lower().strip()
    rewritten: List[str] = [query]

    # Synonym expansion
    for term, expansions in QUERY_REWRITE_RULES.items():
        if term.lower() in query_lower:
            for expansion in expansions:
                variant = query_lower.replace(term.lower(), expansion)
                if variant != query_lower and variant not in rewritten:
                    rewritten.append(variant)

    # Intent-based templates
    templates = INTENT_TEMPLATES.get(intent, [])
    for template in templates:
        variant = template.replace("{query}", query)
        if variant != query and variant not in rewritten:
            rewritten.append(variant)

    return rewritten


class QueryRewriteService:
    """Query rewriting service with rule + LLM fallback.

    Args:
        llm_client: Optional LLM client override for testing.
    """

    def __init__(self, llm_client=None):
        if llm_client is not None:
            self._llm = llm_client
        else:
            from app.llm.client import llm_client as _llm
            self._llm = _llm

    async def rewrite(
        self,
        query: str,
        intent: str = "general_search",
        use_cache: bool = True,
    ) -> RewriteResult:
        """Rewrite a query using rule + optional LLM fallback.

        Args:
            query: Original user query.
            intent: Recognized intent for template selection.
            use_cache: Whether to check cache first.

        Returns:
            RewriteResult with original and rewritten queries.
        """
        # Layer 1: Rule-based
        rule_queries = _rule_rewrite(query, intent)

        # Layer 2: LLM fallback only if query is complex (> 3 tokens)
        if len(query.split()) > 3:
            try:
                schema = {
                    "type": "object",
                    "properties": {
                        "variants": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 5,
                        }
                    },
                    "required": ["variants"],
                }
                prompt = (
                    f"用户查询：{query}\n\n"
                    f"意图：{intent}\n\n"
                    "请生成最多 5 个查询变体以帮助搜索知识库。"
                )
                result = await self._llm.structured_output(
                    prompt=prompt,
                    schema=schema,
                    temperature=0.3,
                )
                llm_variants = result.get("variants", [])
                # Merge: rule variants first, then LLM variants (deduped)
                seen = set(rule_queries)
                for v in llm_variants:
                    if v not in seen:
                        seen.add(v)
                        rule_queries.append(v)
            except Exception as exc:
                logger.warning("LLM query rewrite failed, falling back to rules: %s", exc)

        return RewriteResult(
            original_query=query,
            rewritten_queries=rule_queries[:10],
        )


async def rewrite_query(
    query: str,
    intent: str = "general_search",
    use_llm_fallback: bool = True,
    llm_client=None,
) -> RewriteResult:
    """Convenience function for query rewriting.

    Args:
        query: Original user query.
        intent: Recognized intent.
        use_llm_fallback: Whether to use LLM fallback.
        llm_client: Optional LLM client override for testing.

    Returns:
        RewriteResult with rewritten queries.
    """
    if not use_llm_fallback:
        return RewriteResult(
            original_query=query,
            rewritten_queries=_rule_rewrite(query, intent),
        )

    service = QueryRewriteService(llm_client=llm_client)
    return await service.rewrite(query, intent)
