"""Tests for proxy/metering.py — pure unit tests, no network, no DB."""

from __future__ import annotations

import pytest

from proxy.backends.base import UsageData
from proxy.config import CostRate
from proxy.metering import compute_cost, estimate_tokens_tiktoken


class TestComputeCost:
    def test_known_model_calculates_correctly(self):
        rates = {
            "gpt-4o": CostRate(input_per_token=0.0000025, output_per_token=0.00001)
        }
        usage = UsageData(input_tokens=1000, output_tokens=200, source="exact")
        cost = compute_cost("gpt-4o", usage, rates)
        assert cost == pytest.approx(1000 * 0.0000025 + 200 * 0.00001)

    def test_unknown_model_returns_zero(self):
        rates: dict[str, CostRate] = {}
        usage = UsageData(input_tokens=500, output_tokens=100, source="exact")
        assert compute_cost("unknown-model", usage, rates) == 0.0

    def test_zero_tokens_returns_zero(self):
        rates = {"gpt-4o-mini": CostRate(input_per_token=1.0, output_per_token=1.0)}
        usage = UsageData(input_tokens=0, output_tokens=0, source="exact")
        assert compute_cost("gpt-4o-mini", usage, rates) == 0.0

    def test_cost_is_sum_of_input_and_output(self):
        rates = {"test-model": CostRate(input_per_token=2.0, output_per_token=3.0)}
        usage = UsageData(input_tokens=10, output_tokens=5, source="exact")
        assert compute_cost("test-model", usage, rates) == pytest.approx(10 * 2.0 + 5 * 3.0)


class TestEstimateTokensTiktoken:
    def test_returns_estimated_source(self):
        messages = [{"role": "user", "content": "Hello!"}]
        result = estimate_tokens_tiktoken(messages)
        assert result.source == "estimated"

    def test_returns_positive_input_tokens(self):
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is 2 + 2?"},
        ]
        result = estimate_tokens_tiktoken(messages)
        assert result.input_tokens > 0

    def test_output_tokens_is_zero(self):
        messages = [{"role": "user", "content": "Estimate me"}]
        result = estimate_tokens_tiktoken(messages)
        assert result.output_tokens == 0

    def test_longer_content_gives_more_tokens(self):
        short_msgs = [{"role": "user", "content": "Hi"}]
        long_msgs = [{"role": "user", "content": "Hi " * 200}]
        short_result = estimate_tokens_tiktoken(short_msgs)
        long_result = estimate_tokens_tiktoken(long_msgs)
        assert long_result.input_tokens > short_result.input_tokens


class TestCostRateConfig:
    def test_unconfigured_model_returns_zero_cost(self):
        rates: dict[str, CostRate] = {}
        usage = UsageData(input_tokens=100, output_tokens=50, source="exact")
        assert compute_cost("unconfigured-model", usage, rates) == 0.0

    def test_cost_uses_rate_passed_in_not_cached(self):
        # Rates are dicts passed at call time — changing the dict changes the cost
        rates = {"gpt-4o": CostRate(input_per_token=0.001, output_per_token=0.002)}
        usage = UsageData(input_tokens=100, output_tokens=50, source="exact")
        cost_v1 = compute_cost("gpt-4o", usage, rates)

        # Simulate rate update
        rates["gpt-4o"] = CostRate(input_per_token=0.002, output_per_token=0.004)
        cost_v2 = compute_cost("gpt-4o", usage, rates)

        assert cost_v2 == pytest.approx(cost_v1 * 2)

    def test_unconfigured_model_token_count_source_unchanged(self):
        # token_count_source is on UsageData, not affected by missing rate
        rates: dict[str, CostRate] = {}
        usage = UsageData(input_tokens=10, output_tokens=5, source="estimated")
        compute_cost("no-model", usage, rates)
        assert usage.source == "estimated"
