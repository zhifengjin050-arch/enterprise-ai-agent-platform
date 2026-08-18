"""Entity extraction prompts for the Knowledge Graph Lite.

The LLM extracts named entities from enterprise documents and
classifies them into predefined entity types.
"""
from __future__ import annotations

ENTITY_EXTRACTION_SYSTEM_PROMPT = """你是一位企业知识图谱实体抽取专家。

你的任务是从企业技术文档中识别并抽取命名实体。

支持的实体类型：
- service: 服务（如"订单服务"、"支付服务"）
- component: 组件（如"消息队列"、"缓存层"）
- technology: 技术（如"Redis"、"Kubernetes"、"Docker"）
- tool: 工具（如"Grafana"、"Prometheus"、"Jenkins"）
- team: 团队（如"SRE团队"、"后端团队"）
- person: 人员
- environment: 环境（如"生产环境"、"staging"）
- incident: 事故（如"502故障"、"数据库宕机"）
- sop: SOP / 标准操作流程

规则：
1. 只抽取明确的命名实体，不要编造
2. 每个实体必须有名称和类型
3. 最多抽取20个实体
4. 按重要性排序（最重要的在前）"""

ENTITY_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "实体名称"},
                    "type": {
                        "type": "string",
                        "enum": [
                            "service", "component", "technology", "tool",
                            "team", "person", "environment", "incident", "sop",
                        ],
                        "description": "实体类型",
                    },
                    "description": {
                        "type": "string",
                        "description": "简短描述",
                    },
                },
                "required": ["name", "type"],
            },
            "maxItems": 20,
        },
    },
    "required": ["entities"],
}


def build_entity_extraction_prompt(title: str, content: str) -> str:
    """Build the entity extraction prompt.

    Args:
        title: Document title.
        content: Document content text.

    Returns:
        Formatted prompt string.
    """
    # Truncate content if too long
    truncated = content[:8000] if len(content) > 8000 else content

    return (
        f"### 文档标题\n\n{title}\n\n"
        f"### 文档内容\n\n{truncated}\n\n"
        "请抽取该文档中的命名实体。"
    )
