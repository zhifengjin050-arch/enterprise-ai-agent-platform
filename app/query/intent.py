"""Query intent classification.

Two-layer intent recognition:
1. Rule-based keyword matching (fast, offline)
2. LLM fallback for ambiguous queries

Supported intents:
- incident_analysis: fault/outage related queries
- sop_lookup: procedure/step-by-step queries
- architecture_question: design/structure queries
- configuration_help: config/setup queries
- general_search: anything else
"""

from __future__ import annotations

from dataclasses import dataclass

# ── Intent definitions ─────────────────────────────────

INTENT_RULES: dict = {
    "incident_analysis": [
        "宕机",
        "故障",
        "挂了",
        "崩溃",
        "outage",
        "down",
        "502",
        "503",
        "500",
        "crash",
        "panic",
        "异常",
        "不可用",
        "unavailable",
        "timeout",
        "超时",
        "告警",
        "alert",
        "error",
        "错误",
        "事故",
    ],
    "sop_lookup": [
        "怎么",
        "如何",
        "步骤",
        "排查",
        "处理",
        "操作流程",
        "how to",
        "steps",
        "步骤",
        "解决",
        "修复",
        "fix",
        "troubleshoot",
        "恢复",
        "recover",
        "rollback",
        "回滚",
    ],
    "architecture_question": [
        "架构",
        "设计",
        "拓扑",
        "结构",
        "architecture",
        "design",
        "topology",
        "部署架构",
        "系统设计",
        "模块",
        "component",
        "组件",
        "service mesh",
    ],
    "configuration_help": [
        "配置",
        "config",
        "设置",
        "参数",
        "安装",
        "部署",
        "setup",
        "installation",
        "参数设置",
        "环境",
        "环境变量",
        "environment",
        "yaml",
        "json",
        "toml",
        "ini",
    ],
}


@dataclass
class QueryIntent:
    """Recognized query intent with confidence.

    Attributes:
        intent: Intent category name.
        confidence: Recognition confidence (0.0 to 1.0).
        original_query: The original user query.
    """

    intent: str = "general_search"
    confidence: float = 0.0
    original_query: str = ""


def classify_intent(
    query: str,
    use_llm_fallback: bool = True,
    llm_client=None,
) -> QueryIntent:
    """Two-layer query intent classification.

    Args:
        query: User's natural language query.
        use_llm_fallback: Whether to use LLM fallback.
        llm_client: Optional LLM client for testing.

    Returns:
        QueryIntent with recognized intent and confidence.
    """
    query_lower = query.lower().strip()
    if not query_lower:
        return QueryIntent(
            intent="general_search",
            confidence=1.0,
            original_query=query,
        )

    # Layer 1: Rule-based
    scores: dict = {}
    for intent_name, keywords in INTENT_RULES.items():
        score = sum(1 for kw in keywords if kw.lower() in query_lower)
        if score > 0:
            scores[intent_name] = score

    if scores:
        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]
        confidence = min(1.0, 0.3 + best_score * 0.2)
        return QueryIntent(
            intent=best_intent,
            confidence=round(confidence, 2),
            original_query=query,
        )

    return QueryIntent(
        intent="general_search",
        confidence=0.3,
        original_query=query,
    )
