"""
Classification prompts for determining document type.

DocType values: sop, incident, best_practice, architecture,
configuration, runbook, manual, onboarding, changelog, other.
"""

# System prompt for document classification
CLASSIFICATION_SYSTEM_PROMPT = """你是一位专业的 DevOps 知识库分类专家。
你的任务是根据文档的标题和内容，将其分类到最合适的文档类型。

可选的文档类型：
- sop: 标准操作流程 (Standard Operating Procedure)，包含操作步骤、排查步骤、处理流程
- incident: 故障/事故报告，包含故障复盘、根因分析、影响范围
- best_practice: 最佳实践、推荐方案、规范指南
- architecture: 架构设计、系统设计、技术方案
- configuration: 配置指南、安装部署、参数配置
- runbook: 运维操作手册，包含各种运维操作指令
- manual: 用户手册、使用指南
- onboarding: 入职指南、新环境搭建
- changelog: 变更日志、版本更新记录
- other: 其他类型

请基于文档的实际内容判断类型，不要仅仅依赖关键词。"""

# Classification output schema
CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "doc_type": {
            "type": "string",
            "enum": [
                "sop",
                "incident",
                "best_practice",
                "architecture",
                "configuration",
                "runbook",
                "manual",
                "onboarding",
                "changelog",
                "other",
            ],
            "description": "The classified document type.",
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Confidence score for the classification (0.0 to 1.0).",
        },
        "reason": {
            "type": "string",
            "description": "Brief explanation of why this classification was chosen.",
        },
    },
    "required": ["doc_type", "confidence", "reason"],
}


def build_classification_prompt(title: str, content: str) -> str:
    """Build the classification prompt for a document.

    Args:
        title: Document title.
        content: Document markdown content (truncated if needed).

    Returns:
        Formatted prompt string.
    """
    truncated = content[:4000] if len(content) > 4000 else content
    return f"""请对以下 DevOps 知识文档进行分类。

文档标题：{title}

文档内容：
{truncated}

请分析文档内容并输出其文档类型、置信度和理由。"""
