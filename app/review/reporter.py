"""Knowledge base quality report generator.

Generates formatted quality reports for the knowledge base.
Supports markdown and JSON output formats.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.review.analyzer import generate_health_report


async def generate_markdown_report(session: AsyncSession) -> str:
    """Generate a markdown-formatted knowledge base health report.

    Args:
        session: Database session.

    Returns:
        Markdown report string.
    """
    health = await generate_health_report(session)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        "# 知识库健康度报告",
        "",
        f"**生成时间**: {now}",
        "",
        "## 概览",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 文档总数 | {health.total_documents} |",
        f"| 活跃文档 | {health.active_documents} |",
        f"| 过期文档 | {health.expired_documents} |",
        f"| 平均完整度 | {health.avg_completeness:.1%} |",
        f"| 平均新鲜度 | {health.avg_freshness:.1%} |",
        f"| 疑似重复 | {health.duplicate_count} |",
        "",
    ]

    if health.recommendations:
        lines.extend(
            [
                "## 改进建议",
                "",
            ]
        )
        for rec in health.recommendations:
            lines.append(f"- {rec}")
        lines.append("")

    lines.extend(
        [
            "## 文档详情",
            "",
        ]
    )

    for doc in health.documents:
        status_icon = "EXPIRED" if doc.is_expired else "ACTIVE"
        dup_info = (
            f" (疑似重复: doc #{doc.duplicate_of}, 相似度: {doc.duplicate_score:.1%})"
            if doc.duplicate_of
            else ""
        )

        lines.extend(
            [
                f"### [{status_icon}] {doc.title} (ID: {doc.document_id})",
                "",
                f"- 完整度: {doc.completeness_score:.1%}",
                f"- 新鲜度: {doc.freshness_score:.1%}",
                f"{dup_info}",
            ]
        )

        if doc.missing_sections:
            lines.append(f"- 缺失部分: {', '.join(doc.missing_sections)}")
        if doc.suggestions:
            for s in doc.suggestions:
                lines.append(f"- 建议: {s}")

        lines.append("")

    return "\n".join(lines)


async def generate_json_report(session: AsyncSession) -> dict:
    """Generate a JSON-formatted knowledge base health report.

    Args:
        session: Database session.

    Returns:
        Dict with report data.
    """
    health = await generate_health_report(session)
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "summary": {
            "total_documents": health.total_documents,
            "active_documents": health.active_documents,
            "expired_documents": health.expired_documents,
            "avg_completeness": round(health.avg_completeness, 4),
            "avg_freshness": round(health.avg_freshness, 4),
            "duplicate_count": health.duplicate_count,
        },
        "recommendations": health.recommendations,
        "documents": [d.to_dict() for d in health.documents],
    }
