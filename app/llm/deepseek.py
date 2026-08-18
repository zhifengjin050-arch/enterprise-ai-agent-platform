"""DeepSeek LLM service implementation.

Extends the OpenAI-compatible provider for DeepSeek-specific defaults.
DeepSeek API is fully OpenAI-compatible, so this delegates to
OpenAICompatibleLLM with DeepSeek default settings.
"""

from __future__ import annotations

from typing import Optional

from app.core.config import get_settings
from app.llm.client import OpenAICompatibleLLM


class DeepSeekLLM(OpenAICompatibleLLM):
    """DeepSeek LLM provider with DeepSeek-specific defaults.

    Delegates to the OpenAI-compatible implementation since DeepSeek
    uses the same API format. Sets model to 'deepseek-chat' by default.

    Args:
        api_key: DeepSeek API key. Defaults to settings.deepseek_api_key.
        base_url: API base URL. Defaults to settings.deepseek_base_url.
        model: Model name. Defaults to "deepseek-chat".
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "deepseek-chat",
    ):
        settings = get_settings()
        resolved_key = api_key or settings.deepseek_api_key or settings.llm_api_key
        resolved_url = (
            base_url
            or settings.deepseek_base_url
            or settings.llm_base_url
        ).rstrip("/")
        super().__init__(
            api_key=resolved_key,
            base_url=resolved_url,
            model=model or settings.llm_model or "deepseek-chat",
        )

    def get_model_name(self) -> str:
        """Return the model identifier."""
        return f"deepseek:{self.model}"
