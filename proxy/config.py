"""
proxy/config.py

Loads Relay configuration from config.yml (required at startup) and supports
environment-variable overrides for secrets.

Usage:
    from proxy.config import load_config, RelayConfig
    config = load_config()           # reads config.yml from CWD
    config = load_config("path/to/config.yml")
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class BackendConfig(BaseModel):
    """Configuration for the upstream LLM backend."""

    type: str  # "openai_compat" | "ollama"
    base_url: str
    api_key: str | None = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"openai_compat", "ollama"}
        if v not in allowed:
            raise ValueError(f"backend.type must be one of {allowed!r}, got {v!r}")
        return v

    @field_validator("base_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")


class ApiKey(BaseModel):
    """A client API key accepted by the proxy."""

    key: str
    label: str


class CostRate(BaseModel):
    """Per-token cost rate for a single model."""

    input_per_token: float = Field(ge=0.0)
    output_per_token: float = Field(ge=0.0)


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------


class RelayConfig(BaseModel):
    """Full Relay configuration, parsed from config.yml."""

    backend: BackendConfig
    api_keys: list[ApiKey] = Field(default_factory=list)
    # cost_rates maps model name → CostRate
    cost_rates: dict[str, CostRate] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Env-variable interpolation
# ---------------------------------------------------------------------------

_ENV_VAR_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def _interpolate_env(value: Any) -> Any:
    """
    Recursively walk a YAML-parsed structure and replace ${VAR} tokens with
    the corresponding environment-variable value.  Raises if the variable is
    not set.
    """
    if isinstance(value, str):
        def replacer(m: re.Match[str]) -> str:  # type: ignore[type-arg]
            var = m.group(1)
            result = os.environ.get(var)
            if result is None:
                raise EnvironmentError(
                    f"Config references environment variable ${{{var}}} "
                    f"but it is not set."
                )
            return result

        return _ENV_VAR_RE.sub(replacer, value)

    if isinstance(value, dict):
        return {k: _interpolate_env(v) for k, v in value.items()}

    if isinstance(value, list):
        return [_interpolate_env(item) for item in value]

    return value


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_config(path: str | Path | None = None) -> RelayConfig:
    """
    Load and validate Relay configuration.

    Resolution order:
    1. ``path`` argument (if provided)
    2. ``RELAY_CONFIG`` environment variable
    3. ``config.yml`` in the current working directory

    The ``BACKEND_API_KEY`` environment variable (if set) always overrides
    ``backend.api_key`` from the YAML file, regardless of interpolation.
    """
    if path is None:
        path = os.environ.get("RELAY_CONFIG", "config.yml")

    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Relay config file not found: {config_path.resolve()}\n"
            "Copy config.yml.example to config.yml and fill in your values."
        )

    with config_path.open("r", encoding="utf-8") as fh:
        raw: Any = yaml.safe_load(fh)

    if not isinstance(raw, dict):
        raise ValueError(f"config.yml must be a YAML mapping, got {type(raw).__name__}")

    # Interpolate ${VAR} tokens from environment
    raw = _interpolate_env(raw)

    config = RelayConfig.model_validate(raw)

    # Hard override: BACKEND_API_KEY env var always wins
    env_key = os.environ.get("BACKEND_API_KEY")
    if env_key:
        config.backend.api_key = env_key

    return config
