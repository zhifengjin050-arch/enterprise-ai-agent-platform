"""TaskPlanner — decomposes user questions into ExecutionPlans."""

from __future__ import annotations

import re
from typing import List, Optional

from app.agent_runtime.models import ExecutionPlan, PlanStep
from app.security.intent import Intent, IntentKind, classify_intent

_INCIDENT_HINTS = re.compile(
    r"oom|crash|故障|报错|error|fail|down|超时|timeout|5\d\d",
    re.IGNORECASE,
)
_GRAPH_HINTS = re.compile(
    r"依赖|关系|图谱|entity|关联|belongs|depends|谁负责|owned",
    re.IGNORECASE,
)
_SYNC_HINTS = re.compile(
    r"同步|sync|拉取|connector|飞书|语雀|gitlab",
    re.IGNORECASE,
)
_K8S_HINTS = re.compile(
    r"kubernetes|k8s|pod|deployment|oom|container",
    re.IGNORECASE,
)


class TaskPlanner:
    """Rule-based planner that builds an ExecutionPlan from a user query.

    For production, this can be swapped with an LLM planner while keeping
    the same ExecutionPlan contract.
    """

    def plan(self, query: str, intent: Optional[Intent] = None) -> ExecutionPlan:
        """Create an execution plan for the query.

        Args:
            query: User question.
            intent: Optional pre-classified intent. Secrets produce no tool steps.

        Returns:
            ExecutionPlan with ordered tool steps.
        """
        q = (query or "").strip()
        classified = intent or classify_intent(q)
        if classified.kind == IntentKind.SECRET:
            return ExecutionPlan(steps=[], query=q, rationale="secret_denied")

        steps: List[PlanStep] = []
        rationale_parts: List[str] = []

        # Always start with knowledge search for Q&A style queries
        steps.append(
            PlanStep(
                step=1,
                tool="knowledge_search",
                input={"query": q, "top_n": 5},
                description="检索相关知识文档",
            )
        )
        rationale_parts.append("knowledge_search")

        if classified.kind == IntentKind.HR_SELF:
            return ExecutionPlan(
                steps=steps,
                query=q,
                rationale="hr_self → knowledge_search (caller-bound live HR tools when configured)",
            )

        if classified.kind == IntentKind.ASSET:
            rationale_parts.append("asset_inventory")

        if _GRAPH_HINTS.search(q) or _K8S_HINTS.search(q):
            # Extract a simple entity candidate (first Capitalized / known token)
            entity_name = self._guess_entity(q)
            steps.append(
                PlanStep(
                    step=len(steps) + 1,
                    tool="graph_query",
                    input={"entity_name": entity_name or "Kubernetes", "depth": 1},
                    description="查询知识图谱关联实体",
                )
            )
            rationale_parts.append("graph_query")

        if _INCIDENT_HINTS.search(q):
            steps.append(
                PlanStep(
                    step=len(steps) + 1,
                    tool="knowledge_search",
                    input={
                        "query": f"{q} 故障 根因 解决方案",
                        "top_n": 5,
                    },
                    description="检索历史故障与解决方案",
                )
            )
            rationale_parts.append("incident_search")

        if _SYNC_HINTS.search(q):
            steps.append(
                PlanStep(
                    step=len(steps) + 1,
                    tool="connector_sync",
                    input={"connector_id": "", "sync_mode": "incremental"},
                    description="如需可触发连接器同步（需提供 connector_id）",
                )
            )
            rationale_parts.append("connector_sync")

        return ExecutionPlan(
            steps=steps,
            query=q,
            rationale=" → ".join(rationale_parts),
        )

    @staticmethod
    def _guess_entity(query: str) -> str:
        """Best-effort entity name guess from query tokens."""
        known = [
            "Kubernetes",
            "Docker",
            "Redis",
            "MySQL",
            "PostgreSQL",
            "Nginx",
            "Kafka",
            "Prometheus",
        ]
        ql = query.lower()
        for name in known:
            if name.lower() in ql:
                return name
        # Fallback: first latin word longer than 3 chars
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", query):
            return token
        return ""
