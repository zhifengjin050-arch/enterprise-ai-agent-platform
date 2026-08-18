"""Answer generation prompts for the knowledge Q&A agent.

The LLM receives retrieved context documents and a user query,
and must generate a factual answer with confidence assessment.
"""
from __future__ import annotations

ANSWER_SYSTEM_PROMPT = """你是一位企业 DevOps 知识库智能助手。

你的任务是基于提供的知识文档，回答用户关于 DevOps 技术栈的问题。

规则：
1. 只使用提供的文档内容回答，不要编造信息
2. 如果文档内容不足以回答问题，明确说明"无法从知识库中找到相关信息"
3. 引用具体的文档标题作为来源
4. 用中文回答，技术术语可保留英文
5. 不要输出隐藏的思维链或推理过程
6. 回答应该简洁、准确、实用"""

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {
            "type": "string",
            "description": "最终的答案文本，面向用户。",
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "可信度评分 (0.0-1.0)，基于知识库匹配程度。",
        },
        "reasoning_summary": {
            "type": "string",
            "description": "简短推理摘要（仅用于内部记录，不展示给用户）。",
        },
        "used_sources": {
            "type": "array",
            "items": {"type": "string"},
            "description": "实际使用的源文档标题列表。",
        },
    },
    "required": ["answer", "confidence", "reasoning_summary", "used_sources"],
}


def build_answer_prompt(
    query: str,
    context_text: str,
    history_text: str = "",
) -> str:
    """Build the answer generation prompt.

    Args:
        query: User's original question.
        context_text: Formatted context from retrieved documents.
        history_text: Optional conversation history text.

    Returns:
        Formatted prompt string.
    """
    prompt = ""

    # Include conversation history if available
    if history_text:
        prompt += f"### 对话历史\n\n{history_text}\n\n"

    prompt += f"### 用户问题\n\n{query}\n\n"

    prompt += f"### 知识库文档\n\n{context_text}\n\n"

    prompt += (
        "请基于以上知识库文档回答用户问题。"
        "如果文档不包含相关信息，请如实说明。"
    )

    return prompt
