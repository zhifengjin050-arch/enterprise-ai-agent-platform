"""AI-powered knowledge card generator.

Transforms incident records into structured knowledge cards
for the knowledge base, enabling reuse of incident experience.
"""

from dataclasses import dataclass, field
from typing import List

from app.incident.models import IncidentRecord
from app.llm.client import llm_client


@dataclass
class KnowledgeCard:
    """AI-generated knowledge card from an incident."""

    title: str
    summary: str
    severity: str
    service: str
    root_cause: str
    solution: str
    prevention: List[str] = field(default_factory=list)
    related_sops: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "summary": self.summary,
            "severity": self.severity,
            "service": self.service,
            "root_cause": self.root_cause,
            "solution": self.solution,
            "prevention": self.prevention,
            "related_sops": self.related_sops,
            "tags": self.tags,
        }


async def generate_knowledge_card(incident: IncidentRecord) -> KnowledgeCard:
    """Generate a knowledge card from an incident using AI.

    Args:
        incident: The incident record to generate from.

    Returns:
        Generated KnowledgeCard.
    """
    prompt = f"""基于以下故障记录，生成结构化知识卡片：

故障标题: {incident.title}
影响服务: {incident.service}
严重级别: {incident.severity}
根因: {incident.root_cause or "未记录"}
解决方案: {incident.solution or "未记录"}
影响范围: {incident.impact or "未记录"}
时间线: {incident.timeline or "未记录"}

请生成包含以下内容的知识卡片：
1. 标题：简洁的问题描述
2. 摘要：1-2句话概述
3. 根因分析
4. 解决方案步骤
5. 预防措施（列表）
6. 相关SOP建议（列表）
7. 推荐标签（列表，用于检索）
"""

    response = await llm_client.chat(prompt)

    # Parse AI response into structured card
    return _parse_card_response(
        title=incident.title,
        severity=incident.severity,
        service=incident.service,
        root_cause=incident.root_cause or "",
        solution=incident.solution or "",
        ai_response=response,
    )


async def batch_generate_cards(
    incidents: List[IncidentRecord],
) -> List[KnowledgeCard]:
    """Generate knowledge cards for multiple incidents.

    Args:
        incidents: List of incident records.

    Returns:
        List of generated KnowledgeCards.
    """
    cards = []
    for incident in incidents:
        card = await generate_knowledge_card(incident)
        cards.append(card)
    return cards


def _parse_card_response(
    title: str,
    severity: str,
    service: str,
    root_cause: str,
    solution: str,
    ai_response: str,
) -> KnowledgeCard:
    """Parse AI response into a structured KnowledgeCard.

    Args:
        title: Incident title.
        severity: Incident severity.
        service: Affected service.
        root_cause: Root cause description.
        solution: Solution description.
        ai_response: Raw AI response text.

    Returns:
        Parsed KnowledgeCard.
    """
    sections = ai_response.split("\n\n")
    summary = ""
    prevention: List[str] = []
    related_sops: List[str] = []
    tags: List[str] = []

    for section in sections:
        section_lower = section.lower().strip()

        if section_lower.startswith("摘要") or section_lower.startswith("概述"):
            summary = section.split(":", 1)[-1].strip() if ":" in section else section
        elif section_lower.startswith("预防措施") or section_lower.startswith("建议"):
            lines = section.split("\n")[1:]
            prevention = [
                line.strip().lstrip("- ").lstrip("* ").lstrip("1234567890. ")
                for line in lines
                if line.strip()
            ]
        elif section_lower.startswith("相关sop") or section_lower.startswith("关联流程"):
            lines = section.split("\n")[1:]
            related_sops = [
                line.strip().lstrip("- ").lstrip("* ") for line in lines if line.strip()
            ]
        elif section_lower.startswith("标签") or section_lower.startswith("关键词"):
            line = (
                section.split(":", 1)[-1].strip()
                if ":" in section
                else section.split("\n", 1)[-1].strip()
            )
            tags = [t.strip().lstrip("- ").lstrip("* ") for t in line.split(",") if t.strip()]

    return KnowledgeCard(
        title=title,
        summary=summary or f"{service} {severity} 故障处理经验",
        severity=severity,
        service=service,
        root_cause=root_cause,
        solution=solution,
        prevention=prevention,
        related_sops=related_sops,
        tags=tags,
    )
