"""Context engine for Agent Runtime — assembles LLM context from memory + retrieval."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class ContextEngine:
    """Build prompt context from conversation history and tool sources."""

    def __init__(self, *, max_source_chars: int = 4000) -> None:
        self._max_source_chars = max_source_chars

    def build(
        self,
        *,
        query: str,
        conversation_context: str = "",
        sources: Optional[List[Dict[str, Any]]] = None,
        system_hint: str = "",
    ) -> Dict[str, str]:
        """Assemble system + user prompt blocks.

        Returns:
            Dict with keys: system, user, sources_block.
        """
        sources = sources or []
        parts: List[str] = []
        used = 0
        for s in sources:
            title = s.get("title") or s.get("name") or "source"
            content = str(s.get("content") or s.get("snippet") or "")[:500]
            block = f"[{title}]\n{content}"
            if used + len(block) > self._max_source_chars:
                break
            parts.append(block)
            used += len(block)

        sources_block = "\n\n".join(parts) if parts else "(无检索资料)"
        system = system_hint or (
            "你是企业知识助手。基于提供的资料与对话历史回答问题，"
            "引用资料时保持客观，资料不足时明确说明。"
        )
        history = f"对话历史:\n{conversation_context}\n\n" if conversation_context else ""
        user = f"{history}检索资料:\n{sources_block}\n\n用户问题: {query}\n\n请用中文回答。"
        return {
            "system": system,
            "user": user,
            "sources_block": sources_block,
        }
