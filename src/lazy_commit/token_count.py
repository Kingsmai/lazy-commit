"""Token counting helpers for CLI utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ConfigError

DEFAULT_TOKEN_MODEL = "gpt-4.1-mini"
_FALLBACK_ENCODINGS = ("o200k_base", "cl100k_base")


@dataclass(frozen=True)
class TokenCountResult:
    """Represents token counting metadata and result."""

    token_count: int
    character_count: int
    model_name: str
    encoding_name: str


@dataclass(frozen=True)
class TokenCounter:
    """Reusable token counter bound to a specific model/encoding."""

    model_name: str
    encoding_name: str
    _encoding: Any

    def count(self, text: str) -> int:
        return len(self._encoding.encode(text))

    def truncate(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0:
            return ""
        tokens = self._encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return self._encoding.decode(tokens[:max_tokens])


def _load_tiktoken() -> Any:
    try:
        import tiktoken
    except ImportError as exc:
        raise ConfigError(
            "Token counting requires 'tiktoken'. Install it with: pip install tiktoken"
        ) from exc
    return tiktoken


def _resolve_encoding(
    tiktoken_module: Any,
    *,
    model_name: str,
    encoding_name: str | None,
) -> tuple[str, Any]:
    if encoding_name:
        try:
            return encoding_name, tiktoken_module.get_encoding(encoding_name)
        except KeyError as exc:
            raise ConfigError(f"Unknown token encoding: {encoding_name}") from exc

    try:
        encoding = tiktoken_module.encoding_for_model(model_name)
        return encoding.name, encoding
    except KeyError:
        for fallback_name in _FALLBACK_ENCODINGS:
            try:
                return fallback_name, tiktoken_module.get_encoding(fallback_name)
            except KeyError:
                continue

    raise ConfigError(
        "Unable to resolve tokenizer encoding for model "
        f"'{model_name}'. Pass --token-encoding explicitly."
    )


def create_token_counter(
    *,
    model_name: str = DEFAULT_TOKEN_MODEL,
    encoding_name: str | None = None,
) -> TokenCounter:
    """Create a reusable token counter for one model/encoding pair."""
    tiktoken_module = _load_tiktoken()
    resolved_encoding_name, encoding = _resolve_encoding(
        tiktoken_module,
        model_name=model_name,
        encoding_name=encoding_name,
    )
    return TokenCounter(
        model_name=model_name,
        encoding_name=resolved_encoding_name,
        _encoding=encoding,
    )


def count_tokens(
    text: str,
    *,
    model_name: str = DEFAULT_TOKEN_MODEL,
    encoding_name: str | None = None,
) -> TokenCountResult:
    """Count text tokens with model-aware tiktoken encoding resolution."""
    counter = create_token_counter(
        model_name=model_name,
        encoding_name=encoding_name,
    )
    token_count = counter.count(text)
    return TokenCountResult(
        token_count=token_count,
        character_count=len(text),
        model_name=model_name,
        encoding_name=counter.encoding_name,
    )
