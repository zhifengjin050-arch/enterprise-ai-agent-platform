"""Relation extraction prompts for the Knowledge Graph Lite.

The LLM extracts typed, directed relations between entities
from enterprise document content.
"""

from __future__ import annotations

RELATION_EXTRACTION_SYSTEM_PROMPT = """你是一位企业知识图谱关系抽取专家。

你的任务是从企业技术文档中抽取实体之间的关系。

支持的关系类型：
- depends_on: A 依赖 B（如"订单服务 depends_on Redis"）
- belongs_to: A 属于 B（如"支付模块 belongs_to 订单系统"）
- uses: A 使用 B（如"应用 uses PostgreSQL"）
- related_to: A 与 B 相关（通用关联）
- caused_by: A 由 B 引起（如"502错误 caused_by Redis宕机"）
- solved_by: A 由 B 解决（如"故障 solved_by 重启服务"）
- owned_by: A 由 B 拥有（如"订单服务 owned_by 交易团队"）

规则：
1. 只抽取文档中明确提及的关系
2. 每条关系必须有 source、target、type
3. 置信度0.0-1.0，基于文档中描述的明确程度
4. 最多抽取20条关系"""

RELATION_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "源实体名称",
                    },
                    "target": {
                        "type": "string",
                        "description": "目标实体名称",
                    },
                    "type": {
                        "type": "string",
                        "enum": [
                            "depends_on",
                            "belongs_to",
                            "uses",
                            "related_to",
                            "caused_by",
                            "solved_by",
                            "owned_by",
                        ],
                        "description": "关系类型",
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "置信度",
                    },
                },
                "required": ["source", "target", "type"],
            },
            "maxItems": 20,
        },
    },
    "required": ["relations"],
}


def build_relation_extraction_prompt(
    title: str,
    content: str,
    entities: list,
) -> str:
    """Build the relation extraction prompt.

    Args:
        title: Document title.
        content: Document content text.
        entities: List of extracted entity dicts.

    Returns:
        Formatted prompt string.
    """
    truncated = content[:8000] if len(content) > 8000 else content
    entity_list = "\n".join(f"- {e.get('name', '?')} ({e.get('type', '?')})" for e in entities[:30])

    return (
        f"### 文档标题\n\n{title}\n\n"
        f"### 文档内容\n\n{truncated}\n\n"
        f"### 已识别实体\n\n{entity_list}\n\n"
        "请基于以上文档和实体列表，抽取实体之间的关系。"
    )
