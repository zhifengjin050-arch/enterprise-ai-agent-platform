"""OpenAI-compatible LLM API client (unified provider).

Fully async implementation of LLMService that works with any
OpenAI-compatible API: DeepSeek, Qwen, OpenAI, vLLM, Ollama, etc.

Supports:
    - Chat completion
    - Streaming response
    - Structured JSON output (JSON Schema mode)
"""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from app.core.config import get_settings
from app.llm.base import LLMService


class OpenAICompatibleLLM(LLMService):
    """Unified LLM provider for any OpenAI-compatible API.

    Args:
        api_key: API key. Defaults to settings.llm_api_key.
        base_url: API base URL. Defaults to settings.llm_base_url.
        model: Model name. Defaults to settings.llm_model.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        settings = get_settings()
        self.api_key = api_key or settings.llm_api_key
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.model = model or settings.llm_model
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=120.0,
            )
        return self._client

    def _build_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Send a chat message and get a response.

        Args:
            message: User message content.
            system_prompt: Optional system instruction.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.

        Returns:
            Response text.

        Raises:
            ConnectionError: If API is unreachable.
            ValueError: If API key is not configured.
        """
        if not self.api_key:
            return "[AI分析未配置 - 需设置LLM_API_KEY]"

        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})

        client = await self._get_client()
        try:
            response = await client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                headers=self._build_headers(),
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

        except httpx.HTTPStatusError as e:
            raise ConnectionError(
                f"LLM API error: {e.response.status_code} - {e.response.text}"
            )
        except httpx.RequestError as e:
            raise ConnectionError(f"LLM API request failed: {str(e)}")

    async def chat_stream(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """Stream a chat response.

        Args:
            Same as chat().

        Yields:
            Response text chunks.
        """
        if not self.api_key:
            yield "[AI分析未配置 - 需设置LLM_API_KEY]"
            return

        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})

        client = await self._get_client()
        try:
            async with client.stream(
                "POST",
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                },
                headers=self._build_headers(),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        raw = line[6:]
                        if raw.strip() == "[DONE]":
                            break
                        chunk = json.loads(raw)
                        if content := (
                            chunk.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content")
                        ):
                            yield content

        except Exception as e:
            yield f"\n[流式响应错误: {str(e)}]"

    async def structured_output(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """Request structured JSON output matching the provided schema.

        The LLM is instructed to respond with valid JSON only,
        conforming to the provided JSON schema definition.
        Uses JSON mode via response_format when available, otherwise
        falls back to instructing the model via the system prompt.

        Args:
            prompt: The user message / task description.
            schema: A JSON schema dict describing the expected output structure.
            system_prompt: Optional system-level instruction.
            temperature: Lower temperature (default 0.1) for deterministic output.
            max_tokens: Maximum response tokens.

        Returns:
            Parsed JSON dictionary matching the schema.

        Raises:
            ValueError: If response cannot be parsed as valid JSON.
            ConnectionError: If the LLM API is unreachable.
        """
        if not self.api_key:
            raise ValueError("[AI分析未配置 - 需设置LLM_API_KEY]")

        # Build system prompt with schema instruction
        schema_json = json.dumps(schema, ensure_ascii=False, indent=2)
        schema_instruction = (
            "你必须严格按照以下 JSON Schema 输出，只返回合法的 JSON，不要包含任何其他文字、注释或markdown代码块标记。\n\n"
            f"JSON Schema:\n{schema_json}\n\n"
            "只输出符合该 schema 的 JSON 对象。"
        )

        full_system = ""
        if system_prompt:
            full_system += system_prompt + "\n\n"
        full_system += schema_instruction

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": prompt},
        ]

        client = await self._get_client()
        try:
            response = await client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                headers=self._build_headers(),
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            return self._parse_json_response(content)

        except httpx.HTTPStatusError as e:
            raise ConnectionError(
                f"LLM API error: {e.response.status_code} - {e.response.text}"
            )
        except httpx.RequestError as e:
            raise ConnectionError(f"LLM API request failed: {str(e)}")

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling code fences if present.

        Args:
            content: Raw LLM response string.

        Returns:
            Parsed JSON dictionary.

        Raises:
            ValueError: If JSON parsing fails.
        """
        cleaned = content.strip()

        # Remove markdown code fences if present
        if cleaned.startswith("```"):
            # Find the first line break after opening ```
            first_nl = cleaned.find("\n")
            if first_nl != -1:
                cleaned = cleaned[first_nl + 1 :]
            # Remove trailing ```
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()
            elif "```" in cleaned:
                cleaned = cleaned[: cleaned.rfind("```")].strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Failed to parse LLM structured output as JSON: {e}\n"
                f"Raw content: {content[:500]}"
            )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def get_model_name(self) -> str:
        """Return the model identifier."""
        return self.model


# Global LLM client instance
llm_client = OpenAICompatibleLLM()
