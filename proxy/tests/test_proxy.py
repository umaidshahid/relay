"""
Tests for proxy/routers/proxy.py — unit tests using httpx mock transport.

All tests use an in-memory SQLite database and a mock httpx transport
so no live LLM is required.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from proxy.backends.base import ChatRequest, ChatResponse, UsageData
from proxy.config import ApiKey, BackendConfig, CostRate, RelayConfig
from proxy.main import app


def _make_config(**kwargs) -> RelayConfig:
    defaults: dict[str, Any] = {
        "backend": BackendConfig(type="openai_compat", base_url="http://fake-backend/v1"),
        "api_keys": [ApiKey(key="sk-test-key", label="test-app")],
        "cost_rates": {"gpt-4o-mini": CostRate(input_per_token=0.0001, output_per_token=0.0002)},
    }
    defaults.update(kwargs)
    return RelayConfig(**defaults)


VALID_RESPONSE_BODY = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "model": "gpt-4o-mini",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Hello!"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
}

REQUEST_BODY = {
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hi"}],
}


class TestNonStreamingProxy:
    def test_valid_request_returns_200(self):
        config = _make_config()

        mock_usage = UsageData(input_tokens=10, output_tokens=5, source="exact")
        mock_response = ChatResponse(body=VALID_RESPONSE_BODY, status_code=200)

        with (
            patch.object(app, "state", MagicMock(config=config)),
            patch("proxy.routers.proxy.OpenAICompatAdapter") as mock_adapter_cls,
            patch("proxy.routers.proxy._write_record", new_callable=AsyncMock),
        ):
            mock_adapter = AsyncMock()
            mock_adapter.chat_complete.return_value = (mock_response, mock_usage)
            mock_adapter_cls.return_value = mock_adapter

            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/v1/chat/completions",
                json=REQUEST_BODY,
                headers={"Authorization": "Bearer sk-test-key"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "chatcmpl-test"

    def test_invalid_key_returns_401(self):
        config = _make_config()
        with patch.object(app, "state", MagicMock(config=config)):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/v1/chat/completions",
                json=REQUEST_BODY,
                headers={"Authorization": "Bearer wrong-key"},
            )
        assert resp.status_code == 401

    def test_missing_auth_returns_401(self):
        config = _make_config()
        with patch.object(app, "state", MagicMock(config=config)):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/v1/chat/completions", json=REQUEST_BODY)
        assert resp.status_code == 401


class TestOllamaAdapter:
    """Unit tests for OllamaAdapter token extraction."""

    def test_extracts_exact_tokens_from_ollama_response(self):
        from proxy.backends.ollama import OllamaAdapter
        from proxy.backends.base import UsageData

        adapter = OllamaAdapter(base_url="http://fake-ollama:11434")

        ollama_body = {
            "model": "llama3",
            "message": {"role": "assistant", "content": "Hi!"},
            "prompt_eval_count": 42,
            "eval_count": 8,
            "done": True,
        }
        usage = adapter._extract_usage(ollama_body)
        assert usage is not None
        assert usage.source == "exact"
        assert usage.input_tokens == 42
        assert usage.output_tokens == 8

    def test_falls_back_to_estimated_when_counts_absent(self):
        from proxy.backends.ollama import OllamaAdapter

        adapter = OllamaAdapter(base_url="http://fake-ollama:11434")
        ollama_body = {"model": "llama3", "message": {"role": "assistant", "content": "Hi!"}}
        usage = adapter._extract_usage(ollama_body)
        assert usage is None  # caller handles fallback
