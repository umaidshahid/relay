"""Tests for proxy/auth.py — pure unit tests, no network, no DB."""

from __future__ import annotations

import pytest

from proxy.auth import authenticate_key
from proxy.config import ApiKey

KEYS = [
    ApiKey(key="sk-relay-abc123", label="my-app"),
    ApiKey(key="sk-relay-def456", label="staging"),
]


class TestAuthenticateKey:
    def test_valid_key_returns_api_key(self):
        result = authenticate_key("Bearer sk-relay-abc123", KEYS)
        assert result is not None
        assert result.label == "my-app"

    def test_second_valid_key_returns_correct_entry(self):
        result = authenticate_key("Bearer sk-relay-def456", KEYS)
        assert result is not None
        assert result.label == "staging"

    def test_unknown_key_returns_none(self):
        result = authenticate_key("Bearer sk-relay-notreal", KEYS)
        assert result is None

    def test_missing_header_returns_none(self):
        result = authenticate_key(None, KEYS)
        assert result is None

    def test_empty_header_returns_none(self):
        result = authenticate_key("", KEYS)
        assert result is None

    def test_malformed_header_no_bearer_returns_none(self):
        result = authenticate_key("sk-relay-abc123", KEYS)
        assert result is None

    def test_case_insensitive_bearer_prefix(self):
        result = authenticate_key("BEARER sk-relay-abc123", KEYS)
        assert result is not None
        assert result.label == "my-app"

    def test_empty_key_list_returns_none(self):
        result = authenticate_key("Bearer sk-relay-abc123", [])
        assert result is None
