"""Custom errors used by lazy-commit."""


class LazyCommitError(Exception):
    """Base error for lazy-commit."""


class ConfigError(LazyCommitError):
    """Raised when required configuration is missing or invalid."""


class GitError(LazyCommitError):
    """Raised when git operations fail."""


class LLMError(LazyCommitError):
    """Raised when model invocation or parsing fails."""

