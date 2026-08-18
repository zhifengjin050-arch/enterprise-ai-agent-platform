"""
Tag generation prompts for extracting knowledge tags from documents.

Produces up to 10 relevant tags based on document content.
"""

# System prompt for tag generation
TAG_GENERATION_SYSTEM_PROMPT = """你是一位 DevOps 知识标签专家。
你的任务是根据文档内容生成相关的知识标签。

标签应覆盖以下方面：
- 技术栈（如 kubernetes, docker, linux, nginx, python）
- 工具（如 prometheus, grafana, jenkins, gitlab）
- 领域概念（如 monitoring, security, networking, database）
- 文档类型特征（如 troubleshooting, tutorial, reference）

要求：
1. 输出最多 10 个标签
2. 标签使用英文小写
3. 每个标签应是单个词或常用复合词（如 ci_cd, load_balancing）
4. 优先匹配已有标签（如果文档内容明确涉及某技术）
5. 避免生成过于宽泛或无关的标签"""

TAG_GENERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 10,
            "description": "List of up to 10 relevant knowledge tags.",
        }
    },
    "required": ["tags"],
}


def build_tag_generation_prompt(title: str, content: str) -> str:
    """Build the tag generation prompt for a document.

    Args:
        title: Document title.
        content: Document markdown content (truncated if needed).

    Returns:
        Formatted prompt string.
    """
    truncated = content[:4000] if len(content) > 4000 else content
    return f"""请为以下 DevOps 知识文档生成标签。

文档标题：{title}

文档内容：
{truncated}

请分析文档的技术领域和关键概念，生成最多 10 个相关的知识标签。"""
