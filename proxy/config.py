"""
proxy/config.py

Loads Relay configuration from config.yml and environment variables.

config.yml holds only operator-level settings (cost rates).
Per-user backend credentials are stored in the DB (proxy/db/models.py).

Required environment variables (fail fast at startup if absent):
  RELAY_ENCRYPT_KEY — Fernet key for encrypting provider credentials
  JWT_SECRET        — signing secret for FastAPI-Users JWT tokens

Usage:
    from proxy.config import load_config, RelayConfig
    config = load_config()
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class CostRate(BaseModel):
    """Per-token cost rate for a single model (operator-configured)."""

    input_per_token: float = Field(ge=0.0)
    output_per_token: float = Field(ge=0.0)


class RelayConfig(BaseModel):
    """Operator-level configuration parsed from config.yml."""

    # cost_rates maps model name → CostRate; loaded at startup
    cost_rates: dict[str, CostRate] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Env-variable interpolation
# ---------------------------------------------------------------------------

_ENV_VAR_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def _interpolate_env(value: Any) -> Any:
    if isinstance(value, str):
        def replacer(m: re.Match) -> str:
            var = m.group(1)
            result = os.environ.get(var)
            if result is None:
                raise EnvironmentError(
                    f"Config references environment variable ${{{var}}} but it is not set."
                )
            return result
        return _ENV_VAR_RE.sub(replacer, value)
    if isinstance(value, dict):
        return {k: _interpolate_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env(item) for item in value]
    return value


# ---------------------------------------------------------------------------
# Startup secrets validation
# ---------------------------------------------------------------------------

def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(
            f"Required environment variable {name!r} is not set. "
            "Set it before starting Relay."
        )
    return value


def validate_required_env() -> None:
    """Fail fast at startup if required secrets are absent."""
    _require_env("RELAY_ENCRYPT_KEY")
    _require_env("JWT_SECRET")


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(path: str | Path | None = None) -> RelayConfig:
    """Load and validate operator-level Relay configuration.

    Resolution order for path:
    1. path argument (if provided)
    2. RELAY_CONFIG environment variable
    3. config.yml in the current working directory

    config.yml is optional — if absent or empty, an empty config (no cost
    rates) is returned so the server starts without it. Models with no
    configured rate simply record their cost as 0.0.
    """
    if path is None:
        path = os.environ.get("RELAY_CONFIG", "config.yml")

    config_path = Path(path)
    if not config_path.exists():
        return RelayConfig()

    with config_path.open("r", encoding="utf-8") as fh:
        raw: Any = yaml.safe_load(fh)

    if raw is None:
        return RelayConfig()

    if not isinstance(raw, dict):
        raise ValueError(f"config.yml must be a YAML mapping, got {type(raw).__name__}")

    raw = _interpolate_env(raw)
    return RelayConfig.model_validate(raw)
