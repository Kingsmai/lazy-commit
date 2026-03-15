"""Custom errors used by lazy-commit."""

from __future__ import annotations

from typing import Sequence


class LazyCommitError(Exception):
    """Base error for lazy-commit."""


class ConfigError(LazyCommitError):
    """Raised when required configuration is missing or invalid."""


class GitError(LazyCommitError):
    """Raised when git operations fail."""


class LLMError(LazyCommitError):
    """Raised when model invocation or parsing fails."""

    def __init__(
        self,
        message: str,
        *,
        details: Sequence[str] = (),
        hints: Sequence[str] = (),
    ) -> None:
        super().__init__(message)
        self.details = tuple(detail for detail in details if detail)
        self.hints = tuple(hint for hint in hints if hint)
