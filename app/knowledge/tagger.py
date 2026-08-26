"""
Tagging system for knowledge documents.

Two-layer tag generation:
1. Rule-based keyword extraction (fast)
2. AI tag generator (LLM fallback)

Supports:
- Existing tag matching (prefer known tags)
- Max 10 tags limit
- Cache to prevent infinite generation
"""

from __future__ import annotations

import re
import uuid
from typing import Dict, List, Optional, Set, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.models import DocumentStatus, KnowledgeDocument, KnowledgeTag
from app.llm.cache import cached_call, store_cached_result
from app.prompts.tag_generation import (
    TAG_GENERATION_SCHEMA,
    TAG_GENERATION_SYSTEM_PROMPT,
    build_tag_generation_prompt,
)

# Known predefined tag keywords for rule-based extraction
TAG_KEYWORDS: Dict[str, List[str]] = {
    "kubernetes": ["kubernetes", "k8s", "pod", "deployment", "service", "kube"],
    "docker": ["docker", "container", "dockerfile", "compose"],
    "linux": ["linux", "ubuntu", "centos", "bash", "shell", "unix"],
    "network": ["network", "tcp", "dns", "负载均衡", "nginx", "http"],
    "database": ["database", "mysql", "postgresql", "redis", "sql", "mongo"],
    "security": ["security", "安全", "vulnerability", "cve", "ssl", "tls"],
    "monitoring": ["monitoring", "监控", "prometheus", "grafana", "告警", "alert"],
    "ci_cd": ["ci/cd", "jenkins", "gitlab ci", "github actions", "pipeline", "ci"],
    "cloud": ["cloud", "aws", "azure", "gcp", "阿里云", "aws"],
    "git": ["git", "github", "gitlab", "版本控制", "version control"],
    "python": ["python", "pip", "poetry", "virtualenv"],
    "ansible": ["ansible", "playbook"],
    "terraform": ["terraform", "iac", "infrastructure as code"],
}


def rule_extract_tags(title: str, content: str) -> List[str]:
    """First-layer rule-based tag extraction.

    Args:
        title: Document title.
        content: Document markdown content.

    Returns:
        List of tags matched by keywords.
    """
    combined = f"{title}\n{content}".lower()
    tags: List[str] = []

    for tag, keywords in TAG_KEYWORDS.items():
        if any(kw.lower() in combined for kw in keywords):
            tags.append(tag)

    # Deduplicate preserving order, max 10 tags
    seen: Set[str] = set()
    deduped: List[str] = []
    for t in tags:
        if t not in seen and len(deduped) < 10:
            seen.add(t)
            deduped.append(t)

    return deduped


class AITagger:
    """Second-layer AI-based tag generator.

    Uses LLM structured output to generate up to 10 relevant tags.
    Results are cached based on document content hash.
    """

    def __init__(self, llm_client=None):
        """Initialize with optional LLM client override for testing.

        Args:
            llm_client: LLM service instance. Defaults to global llm_client.
        """
        if llm_client is not None:
            self._llm = llm_client
        else:
            from app.llm.client import llm_client as _llm

            self._llm = _llm

    async def generate_tags(
        self,
        title: str,
        content: str,
        existing_tags: Optional[List[str]] = None,
        use_cache: bool = True,
    ) -> List[str]:
        """Generate tags using LLM with structured output.

        Args:
            title: Document title.
            content: Document markdown content.
            existing_tags: Optional list of existing tags to prefer.
            use_cache: Whether to check cache first.

        Returns:
            List of up to 10 generated tags.
        """
        # Check cache
        if use_cache:
            cached_value, hit = cached_call(
                prompt="",
                use_content_hash=True,
                content=content,
                content_title=title,
            )
            if hit and isinstance(cached_value, dict):
                tags = cached_value.get("tags", [])
                return self._normalize_tags(tags, existing_tags)

        # Build prompt with existing tag hints
        prompt = build_tag_generation_prompt(title, content)
        if existing_tags:
            prompt += f"\n\n已有标签供参考（优先匹配）：{', '.join(existing_tags)}"

        try:
            result = await self._llm.structured_output(
                prompt=prompt,
                schema=TAG_GENERATION_SCHEMA,
                system_prompt=TAG_GENERATION_SYSTEM_PROMPT,
                temperature=0.1,
            )

            tags = result.get("tags", [])
            tags = self._normalize_tags(tags, existing_tags)

            # Cache result
            if use_cache:
                store_cached_result(
                    prompt="",
                    result={"tags": tags},
                    use_content_hash=True,
                    content=content,
                    content_title=title,
                )

            return tags

        except (ValueError, ConnectionError) as e:
            return [f"_tag_error: {e}"]

    def _normalize_tags(
        self,
        tags: List[str],
        existing_tags: Optional[List[str]] = None,
    ) -> List[str]:
        """Normalize and deduplicate tag list.

        Ensures:
        - Max 10 tags
        - Deduplicated
        - Existing tags preferred if matched

        Args:
            tags: Raw tags from LLM.
            existing_tags: Optional list of existing tags to prefer.

        Returns:
            Normalized list of up to 10 tags.
        """
        # Clean and normalize
        normalized: List[str] = []
        seen: Set[str] = set()

        for tag in tags[:20]:  # Process up to 20 raw tags
            cleaned = tag.strip().lower().replace(" ", "_").replace("-", "_").replace("/", "_")
            cleaned = re.sub(r"[^a-z0-9_]", "", cleaned)
            if cleaned and cleaned not in seen and len(cleaned) <= 50:
                seen.add(cleaned)
                normalized.append(cleaned)

        # If existing tags are provided, prefer them by reordering
        if existing_tags:
            existing_lower = {t.lower(): t for t in existing_tags}
            # Move existing tags to front if they appear
            preferred = [t for t in normalized if t.lower() in existing_lower]
            others = [t for t in normalized if t.lower() not in existing_lower]
            normalized = preferred + others

        return normalized[:10]


async def generate_tags(
    title: str,
    content: str,
    use_llm_fallback: bool = True,
    llm_client=None,
) -> List[str]:
    """Two-layer tag generation.

    Strategy:
        1. Run rule-based extraction first.
        2. If few (<3) tags extracted, fall back to AI tagger.

    Args:
        title: Document title.
        content: Document markdown content.
        use_llm_fallback: Whether to use LLM fallback.
        llm_client: Optional LLM client override for testing.

    Returns:
        List of generated tags.
    """
    # Layer 1: Rule-based
    rule_tags = rule_extract_tags(title, content)

    # If we have enough tags from rules, use them
    if len(rule_tags) >= 3:
        return rule_tags[:10]

    # Layer 2: LLM Fallback
    if use_llm_fallback:
        tagger = AITagger(llm_client=llm_client)
        ai_tags = await tagger.generate_tags(title, content)

        # Merge rule tags with AI tags, prefer rule tags
        merged = list(dict.fromkeys(rule_tags + ai_tags))
        return merged[:10]

    return rule_tags[:10]


# ──────────────────────────────────────────────
# Original database functions (unchanged)
# ──────────────────────────────────────────────


async def get_or_create_tag(
    session: AsyncSession,
    name: str,
    color: Optional[str] = None,
) -> KnowledgeTag:
    """Get an existing tag or create a new one.

    Args:
        session: Database session.
        name: Tag name.
        color: Unused compatibility arg (description preferred).

    Returns:
        KnowledgeTag instance.
    """
    _ = color
    result = await session.execute(select(KnowledgeTag).where(KnowledgeTag.name == name))
    tag = result.scalar_one_or_none()
    if tag is None:
        tag = KnowledgeTag(name=name)
        session.add(tag)
        await session.flush()
        await session.refresh(tag)
    return tag


async def add_tags_to_document(
    session: AsyncSession,
    document_id: Union[str, uuid.UUID],
    tag_names: List[str],
) -> KnowledgeDocument:
    """Add tags to a document."""
    result = await session.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == uuid.UUID(str(document_id)))
    )
    document = result.scalar_one_or_none()
    if not document:
        raise ValueError(f"Document {document_id} not found")

    for tag_name in tag_names:
        tag = await get_or_create_tag(session, tag_name.strip())
        if tag not in document.tags:
            document.tags.append(tag)

    await session.flush()
    await session.refresh(document)
    return document


def extract_tags_from_content(content: str) -> Set[str]:
    """Extract potential tags from document content (#tag / [tag])."""
    tags: Set[str] = set()
    tags.update(re.findall(r"#(\w+)", content))
    tags.update(re.findall(r"\[(\w+)\]", content))
    return tags


async def search_by_tag(session: AsyncSession, tag_name: str) -> List[KnowledgeDocument]:
    """Find all non-archived documents with a specific tag."""
    result = await session.execute(
        select(KnowledgeDocument)
        .join(KnowledgeDocument.tags)
        .where(KnowledgeTag.name == tag_name)
        .where(KnowledgeDocument.status != DocumentStatus.ARCHIVED)
    )
    return list(result.scalars().all())
