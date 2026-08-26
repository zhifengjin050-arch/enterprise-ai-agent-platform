"""Tests for LLM structured_output functionality.

All tests mock the LLM client to avoid real API calls.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm.client import OpenAICompatibleLLM


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """Create a mock LLM client with structured_output support."""
    mock = AsyncMock(spec=OpenAICompatibleLLM)

    async def _structured_output(
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        return {
            "doc_type": "sop",
            "confidence": 0.92,
            "reason": "Contains operational steps and rollback plan.",
        }

    mock.structured_output = _structured_output
    mock.get_model_name.return_value = "mock-model"
    return mock


class TestOpenAICompatibleLLMStructuredOutput:
    """Tests for OpenAICompatibleLLM.structured_output()."""

    @pytest.mark.asyncio
    async def test_structured_output_no_api_key(self) -> None:
        """Without api_key, structured_output should raise ValueError."""
        client = OpenAICompatibleLLM(api_key="", model="test-model")
        with pytest.raises(ValueError, match="AI分析未配置"):
            await client.structured_output(
                prompt="Classify this",
                schema={"type": "object", "properties": {}},
            )

    @pytest.mark.asyncio
    async def test_structured_output_success(self) -> None:
        """Successful call should return parsed JSON matching schema."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        async def mock_post(*args: Any, **kwargs: Any) -> MagicMock:
            mock_response.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"doc_type": "sop", "confidence": 0.92, '
                                '"reason": "Contains operational steps."}'
                            )
                        }
                    }
                ]
            }
            return mock_response

        with patch.object(OpenAICompatibleLLM, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_get_client.return_value = mock_client

            client = OpenAICompatibleLLM(
                api_key="test-key",
                base_url="https://api.test.com/v1",
                model="test-model",
            )
            result = await client.structured_output(
                prompt="Classify this document",
                schema={
                    "type": "object",
                    "properties": {
                        "doc_type": {"type": "string"},
                        "confidence": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                },
            )

        assert result["doc_type"] == "sop"
        assert result["confidence"] == 0.92
        assert "operational" in result["reason"]

    @pytest.mark.asyncio
    async def test_structured_output_with_code_fence(self) -> None:
        """Should handle JSON wrapped in markdown code fences."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        async def mock_post(*args: Any, **kwargs: Any) -> MagicMock:
            mock_response.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '```json\n{"doc_type": "incident", '
                                '"confidence": 0.85, "reason": "Incident report."}\n```'
                            )
                        }
                    }
                ]
            }
            return mock_response

        with patch.object(OpenAICompatibleLLM, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_get_client.return_value = mock_client

            client = OpenAICompatibleLLM(
                api_key="test-key", base_url="https://api.test.com/v1", model="test-model"
            )
            result = await client.structured_output(
                prompt="Classify",
                schema={"type": "object", "properties": {}},
            )

        assert result["doc_type"] == "incident"
        assert result["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_structured_output_invalid_json(self) -> None:
        """Invalid JSON response should raise ValueError."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        async def mock_post(*args: Any, **kwargs: Any) -> MagicMock:
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Not valid json at all"}}]
            }
            return mock_response

        with patch.object(OpenAICompatibleLLM, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_get_client.return_value = mock_client

            client = OpenAICompatibleLLM(
                api_key="test-key",
                base_url="https://api.test.com/v1",
                model="test-model",
            )
            with pytest.raises(ValueError, match="Failed to parse"):
                await client.structured_output(
                    prompt="Classify",
                    schema={"type": "object", "properties": {}},
                )

    @pytest.mark.asyncio
    async def test_structured_output_connection_error(self) -> None:
        """HTTP error should raise ConnectionError."""
        with patch.object(OpenAICompatibleLLM, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.side_effect = ConnectionError("API unreachable")
            mock_get_client.return_value = mock_client

            client = OpenAICompatibleLLM(
                api_key="test-key",
                base_url="https://api.test.com/v1",
                model="test-model",
            )
            with pytest.raises(ConnectionError, match="API unreachable"):
                await client.structured_output(
                    prompt="Classify",
                    schema={"type": "object", "properties": {}},
                )

    def test_parse_json_response_plain(self) -> None:
        """_parse_json_response should handle plain JSON."""
        client = OpenAICompatibleLLM(api_key="test")
        result = client._parse_json_response('{"doc_type": "sop", "confidence": 0.9}')
        assert result["doc_type"] == "sop"
        assert result["confidence"] == 0.9

    def test_parse_json_response_code_fence(self) -> None:
        """_parse_json_response should strip markdown code fences."""
        client = OpenAICompatibleLLM(api_key="test")
        result = client._parse_json_response(
            '```json\n{"doc_type": "incident", "confidence": 0.85}\n```'
        )
        assert result["doc_type"] == "incident"
        assert result["confidence"] == 0.85

    def test_parse_json_response_invalid(self) -> None:
        """_parse_json_response should raise ValueError on invalid input."""
        client = OpenAICompatibleLLM(api_key="test")
        with pytest.raises(ValueError, match="Failed to parse"):
            client._parse_json_response("not json at all")

    def test_get_model_name(self) -> None:
        """get_model_name should return the model identifier."""
        client = OpenAICompatibleLLM(
            api_key="test", base_url="https://api.test.com/v1", model="my-model"
        )
        assert client.get_model_name() == "my-model"


class TestDeepSeekLLM:
    """Tests for DeepSeekLLM provider."""

    def test_deepseek_defaults(self) -> None:
        """DeepSeekLLM should set default model to deepseek-chat."""
        from app.llm.deepseek import DeepSeekLLM

        with patch("app.llm.deepseek.get_settings") as mock_settings:
            mock_settings.return_value.deepseek_api_key = "ds-key"
            mock_settings.return_value.deepseek_base_url = "https://api.deepseek.com/v1"
            mock_settings.return_value.llm_model = "deepseek-chat"

            llm = DeepSeekLLM()
            assert "deepseek" in llm.get_model_name()
            assert llm.model == "deepseek-chat"

    def test_deepseek_explicit_params(self) -> None:
        """Explicit params should override settings."""
        from app.llm.deepseek import DeepSeekLLM

        with patch("app.llm.deepseek.get_settings") as mock_settings:
            mock_settings.return_value.deepseek_api_key = "default-key"

            llm = DeepSeekLLM(
                api_key="custom-key",
                base_url="https://custom.deepseek.com/v1",
                model="deepseek-coder",
            )
            assert llm.api_key == "custom-key"
            assert "custom.deepseek.com" in llm.base_url
            assert llm.model == "deepseek-coder"


class TestLLMServiceIntegration:
    """Integration tests for llm module exports."""

    def test_llm_module_exports(self) -> None:
        """Should export all expected classes."""
        import app.llm as llm_module

        assert hasattr(llm_module, "LLMService")
        assert hasattr(llm_module, "OpenAICompatibleLLM")
        assert hasattr(llm_module, "DeepSeekLLM")
        assert hasattr(llm_module, "llm_client")
        assert hasattr(llm_module, "hash_prompt")
        assert hasattr(llm_module, "hash_document")
        assert hasattr(llm_module, "cached_call")
        assert hasattr(llm_module, "store_cached_result")
        assert hasattr(llm_module, "clear_cache")
        assert hasattr(llm_module, "get_cache_stats")

    def test_llm_client_is_singleton(self) -> None:
        """llm_client should be an OpenAICompatibleLLM instance."""
        from app.llm.client import llm_client

        assert isinstance(llm_client, OpenAICompatibleLLM)
