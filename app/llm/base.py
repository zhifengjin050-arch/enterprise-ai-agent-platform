"""
Abstract base class for LLM service providers.

Defines the unified async interface for LLM interactions.
Supports structured JSON output via the structured_output() method.
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, Optional


class LLMService(ABC):
    """Abstract base class for LLM service providers.

    All LLM providers must implement this abstract base class.
    Supports chat, streaming, and structured JSON output.

    Implementations:
        - OpenAICompatibleLLM (app/llm/client.py)
        - DeepSeekLLM (app/llm/deepseek.py)
        - Future: Qwen, Claude, local models via Ollama/vLLM
    """

    @abstractmethod
    async def chat(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Send a chat message to the LLM and receive a response.

        Args:
            message: The user message content.
            system_prompt: Optional system-level instruction.
            temperature: Sampling temperature (0.0 - 2.0).
            max_tokens: Maximum tokens in the response.

        Returns:
            The LLM's response text.

        Raises:
            ConnectionError: If the LLM API is unreachable.
            ValueError: If API key is not configured.
        """
        ...

    @abstractmethod
    async def chat_stream(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """Stream a chat response from the LLM.

        Args:
            Same as chat().

        Yields:
            Chunks of the response text as they arrive.
        """
        ...
        yield  # pragma: no cover

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier (e.g. 'deepseek-chat')."""
        ...

    @abstractmethod
    async def structured_output(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """Request structured JSON output matching the provided schema.

        The LLM will be instructed to respond with valid JSON only,
        conforming to the provided JSON schema definition.

        Args:
            prompt: The user message / task description.
            schema: A JSON schema dict describing the expected output structure.
            system_prompt: Optional system-level instruction prepended to schema instruction.
            temperature: Lower temperature (default 0.1) for more deterministic output.
            max_tokens: Maximum tokens in the response.

        Returns:
            Parsed JSON dictionary matching the schema.

        Raises:
            ValueError: If the LLM response cannot be parsed as valid JSON.
            ConnectionError: If the LLM API is unreachable.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the underlying HTTP client and release resources."""
        ...
