"""Commit message parsing and normalization."""

from __future__ import annotations

import json
import re
import textwrap
from dataclasses import dataclass

from .errors import LLMError

VALID_TYPES = {
    "feat",
    "fix",
    "docs",
    "style",
    "refactor",
    "perf",
    "test",
    "build",
    "ci",
    "chore",
    "revert",
}
MAX_HEADER_LEN = 72
SCOPE_PATTERN = re.compile(r"^[a-zA-Z0-9._/-]+$")


@dataclass(frozen=True)
class CommitProposal:
    """Structured commit proposal."""

    commit_type: str
    scope: str
    subject: str
    body_lines: list[str]
    breaking_change: bool

    @property
    def header(self) -> str:
        prefix = self.commit_type
        if self.scope:
            prefix += f"({self.scope})"
        header = f"{prefix}: {self.subject}"
        if len(header) <= MAX_HEADER_LEN:
            return header

        # Keep type/scope stable; trim the subject to fit Conventional Commit width.
        keep = max(10, MAX_HEADER_LEN - len(prefix) - 2)
        trimmed_subject = self.subject[: keep - 1].rstrip()
        return f"{prefix}: {trimmed_subject}"

    def to_commit_message(self) -> str:
        chunks = [self.header]
        if self.body_lines:
            wrapped = []
            for line in self.body_lines:
                wrapped.append(textwrap.fill(line, width=100))
            chunks.append("\n".join(wrapped))
        if self.breaking_change:
            breaking_line = "BREAKING CHANGE: behavior is not backward compatible."
            if not self.body_lines:
                chunks.append(breaking_line)
            elif not any(
                line.strip().upper().startswith("BREAKING CHANGE:")
                for line in self.body_lines
            ):
                chunks.append(breaking_line)
        return "\n\n".join(part for part in chunks if part.strip()).strip() + "\n"


def _extract_json_blob(raw: str) -> str:
    stripped = raw.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        # Handle optional json label in fenced output.
        stripped = stripped.replace("json\n", "", 1).strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    match = re.search(r"\{[\s\S]*\}", stripped)
    if not match:
        raise LLMError(
            "Model output did not include a JSON object. "
            f"Raw output snippet: {raw[:200]!r}"
        )
    return match.group(0)


def _normalize_type(value: str) -> str:
    candidate = (value or "").strip().lower()
    return candidate if candidate in VALID_TYPES else "chore"


def _normalize_scope(value: str) -> str:
    scope = (value or "").strip()
    if not scope:
        return ""
    if not SCOPE_PATTERN.match(scope):
        return ""
    return scope


def _normalize_subject(value: str) -> str:
    subject = " ".join((value or "").strip().split())
    subject = subject.rstrip(".")
    if not subject:
        raise LLMError("Model output subject is empty.")
    return subject


def _normalize_body(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        return lines
    if isinstance(value, list):
        lines = [str(item).strip() for item in value if str(item).strip()]
        return lines
    return [str(value).strip()]


def parse_commit_proposal(raw: str) -> CommitProposal:
    """Parse and normalize the model JSON into a commit proposal."""
    blob = _extract_json_blob(raw)
    try:
        data = json.loads(blob)
    except json.JSONDecodeError as exc:
        raise LLMError(
            "Model output could not be parsed as JSON. "
            f"Raw snippet: {raw[:200]!r}"
        ) from exc

    commit_type = _normalize_type(str(data.get("type", "")))
    scope = _normalize_scope(str(data.get("scope", "")))
    subject = _normalize_subject(str(data.get("subject", "")))
    body_lines = _normalize_body(data.get("body"))
    breaking_change = bool(data.get("breaking_change", False))

    return CommitProposal(
        commit_type=commit_type,
        scope=scope,
        subject=subject,
        body_lines=body_lines,
        breaking_change=breaking_change,
    )

