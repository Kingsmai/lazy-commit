"""Prompt template and context trimming."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .git_ops import RepoSnapshot

SYSTEM_PROMPT = """You are an expert software engineer writing high-quality Conventional Commit messages.
Analyze the git changes and return ONLY valid JSON with this schema:
{
  "type": "feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert",
  "scope": "optional short scope or empty string",
  "subject": "imperative mood summary, no trailing period",
  "body": ["optional detail line 1", "optional detail line 2"],
  "breaking_change": false
}
Rules:
- Keep header intent specific and factual.
- Prefer "chore" if uncertain.
- subject should be concise and <= 72 chars when combined with type/scope.
- body lines should be short and meaningful.
- Return JSON only; no markdown fences, no commentary.
"""


@dataclass(frozen=True)
class PromptPayload:
    """Prompt payload for LLM request."""

    system: str
    user: str
    context: str


def _section(title: str, content: str) -> str:
    if not content.strip():
        return ""
    return f"## {title}\n{content.strip()}\n"


def _trim_sections(sections: Iterable[tuple[str, str]], max_chars: int) -> str:
    buffer: list[str] = []
    used = 0
    for title, content in sections:
        rendered = _section(title, content)
        if not rendered:
            continue
        remaining = max_chars - used
        if remaining <= 0:
            break
        if len(rendered) <= remaining:
            buffer.append(rendered)
            used += len(rendered)
            continue

        head = rendered[: max(0, remaining - 20)]
        if head:
            buffer.append(head.rstrip() + "\n...[truncated]\n")
        used = max_chars
        break
    return "\n".join(part.rstrip() for part in buffer if part).strip()


def build_context(snapshot: RepoSnapshot, max_chars: int) -> str:
    """Create context string within user-defined limit."""
    changed = "\n".join(f"- {path}" for path in snapshot.changed_files)
    sections: list[tuple[str, str]] = [
        ("Branch", snapshot.branch),
        ("Changed Files", changed),
        ("Working Tree Status", snapshot.status_short),
        ("Staged Diff", snapshot.staged_diff),
        ("Unstaged Diff", snapshot.unstaged_diff),
        ("Untracked Files", snapshot.untracked_files),
        ("Recent Commit Subjects", snapshot.recent_commits),
    ]
    return _trim_sections(sections, max_chars=max_chars)


def build_prompt(snapshot: RepoSnapshot, max_chars: int) -> PromptPayload:
    """Return model prompts with bounded git context."""
    context = build_context(snapshot, max_chars=max_chars)
    user_prompt = (
        "Generate one normalized conventional commit proposal from the git context.\n"
        "Focus on user-impacting and structural changes, not file-by-file narration.\n\n"
        f"{context}\n"
    )
    return PromptPayload(system=SYSTEM_PROMPT, user=user_prompt, context=context)

