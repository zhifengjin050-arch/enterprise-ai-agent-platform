"""
Quality review prompts for assessing document quality.

Scores across four dimensions:
- Structural Integrity (30%)
- Technical Accuracy (30%)
- Executability (25%)
- Timeliness (15%)
"""

# System prompt for quality analysis
QUALITY_SYSTEM_PROMPT = """你是一位 DevOps 知识库质量评审专家。
你的任务是对知识文档进行全面的质量评估。

评估维度：
1. 结构完整性 (权重 30%)：
   - 文档是否有清晰的标题、章节和小标题
   - 是否有引言/背景说明
   - 是否有目录或导航结构
   - 段落组织是否逻辑清晰

2. 技术准确性 (权重 30%)：
   - 技术描述是否准确
   - 命令、代码、配置是否正确
   - 是否有版本信息
   - 术语使用是否专业

3. 可执行性 (权重 25%)：
   - 操作步骤是否可重复执行
   - 是否有前提条件和依赖说明
   - 是否有预期结果描述
   - 是否有回滚/恢复方案

4. 时效性 (权重 15%)：
   - 文档是否包含版本或日期信息
   - 是否提及适用的软件版本
   - 内容是否可能已过时

评分标准：每维度 0.0-1.0，总分 = sum(维度分 * 权重)

输出应包括：总分、各维度评分、具体问题和改进建议。"""

QUALITY_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Overall quality score (0.0 to 1.0).",
        },
        "structural_integrity": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Structural integrity score (weight 30%).",
        },
        "technical_accuracy": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Technical accuracy score (weight 30%).",
        },
        "executability": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Executability score (weight 25%).",
        },
        "timeliness": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Timeliness score (weight 15%).",
        },
        "issues": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of specific quality issues found.",
        },
        "suggestions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of actionable improvement suggestions.",
        },
    },
    "required": [
        "score",
        "structural_integrity",
        "technical_accuracy",
        "executability",
        "timeliness",
        "issues",
        "suggestions",
    ],
}


def build_quality_prompt(title: str, content: str) -> str:
    """Build the quality review prompt for a document.

    Args:
        title: Document title.
        content: Document markdown content.

    Returns:
        Formatted prompt string.
    """
    truncated = content[:5000] if len(content) > 5000 else content
    return f"""请对以下 DevOps 知识文档进行质量评估。

文档标题：{title}

文档内容：
{truncated}

请从结构完整性、技术准确性、可执行性和时效性四个维度对文档进行评分，
指出存在的问题并提供改进建议。"""
