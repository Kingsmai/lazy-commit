"""Configuration model and environment loading."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .errors import ConfigError

DEFAULT_CONTEXT_SIZE = 12000
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_GEMINI_MODEL = "gemini-3-pro-preview"
OPENAI_PROVIDER = "openai"
GEMINI_PROVIDER = "gemini"


@dataclass(frozen=True)
class Settings:
    """Runtime settings for lazy-commit."""

    api_key: str
    base_url: str | None
    model_name: str
    max_context_size: int
    provider: str
    max_context_tokens: int | None = None

    @property
    def is_gemini(self) -> bool:
        return self.provider == GEMINI_PROVIDER

    @property
    def is_openai(self) -> bool:
        return self.provider == OPENAI_PROVIDER


def _parse_positive_int(value: str, env_name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigError(f"{env_name} must be a positive integer.") from exc

    if parsed <= 0:
        raise ConfigError(f"{env_name} must be a positive integer.")
    return parsed


def detect_provider(model_name: str, base_url: str | None) -> str:
    """Infer provider from model/base URL so the 4 required vars are enough."""
    if base_url and "generativelanguage.googleapis.com" in base_url:
        return GEMINI_PROVIDER
    if model_name.lower().startswith("gemini"):
        return GEMINI_PROVIDER
    return OPENAI_PROVIDER


def load_settings(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model_name: str | None = None,
    max_context_size: int | None = None,
    max_context_tokens: int | None = None,
) -> Settings:
    """Load settings from env vars and optional CLI overrides."""
    env_api_key = os.getenv("LAZY_COMMIT_API_KEY") or os.getenv(
        "LAZY_COMMIT_OPENAI_API_KEY"
    )
    env_base_url = os.getenv("LAZY_COMMIT_BASE_URL") or os.getenv(
        "LAZY_COMMIT_OPENAI_BASE_URL"
    )
    env_model_name = os.getenv("LAZY_COMMIT_OPENAI_MODEL_NAME")
    env_max_context_size = os.getenv("LAZY_COMMIT_MAX_CONTEXT_SIZE")
    env_max_context_tokens = os.getenv("LAZY_COMMIT_MAX_CONTEXT_TOKENS")

    resolved_api_key = (api_key or env_api_key or "").strip()
    if not resolved_api_key:
        raise ConfigError("Missing API key. Set LAZY_COMMIT_API_KEY or pass --api-key.")

    resolved_base_url = (base_url or env_base_url or "").strip() or None
    resolved_model_name = (model_name or env_model_name or "").strip()
    if not resolved_model_name:
        # Choose a default model based on inferred provider from URL.
        provider_for_default = detect_provider("", resolved_base_url)
        resolved_model_name = DEFAULT_GEMINI_MODEL if provider_for_default == GEMINI_PROVIDER else DEFAULT_OPENAI_MODEL

    if max_context_size is not None:
        resolved_max_context_size = max_context_size
    elif env_max_context_size:
        resolved_max_context_size = _parse_positive_int(env_max_context_size, "LAZY_COMMIT_MAX_CONTEXT_SIZE")
    else:
        resolved_max_context_size = DEFAULT_CONTEXT_SIZE

    if resolved_max_context_size <= 0:
        raise ConfigError("max_context_size must be a positive integer.")

    if max_context_tokens is not None:
        resolved_max_context_tokens = max_context_tokens
    elif env_max_context_tokens:
        resolved_max_context_tokens = _parse_positive_int(
            env_max_context_tokens, "LAZY_COMMIT_MAX_CONTEXT_TOKENS"
        )
    else:
        resolved_max_context_tokens = None

    if resolved_max_context_tokens is not None and resolved_max_context_tokens <= 0:
        raise ConfigError("max_context_tokens must be a positive integer.")

    provider = detect_provider(resolved_model_name, resolved_base_url)
    return Settings(
        api_key=resolved_api_key,
        base_url=resolved_base_url,
        model_name=resolved_model_name,
        max_context_size=resolved_max_context_size,
        provider=provider,
        max_context_tokens=resolved_max_context_tokens,
    )
