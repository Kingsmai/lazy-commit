"""Prompt template and context trimming."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .errors import ConfigError
from .git_ops import RepoSnapshot
from .token_count import DEFAULT_TOKEN_MODEL, create_token_counter

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
    token_usage: PromptTokenUsage | None = None


@dataclass(frozen=True)
class PromptTokenUsage:
    """Token estimation and compression information for one prompt build."""

    model_name: str
    encoding_name: str
    context_tokens_before: int
    context_tokens_after: int
    total_tokens_before: int
    total_tokens_after: int
    token_limit: int | None
    compression_applied: bool
    compression_steps: tuple[str, ...]


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


def _build_sections(snapshot: RepoSnapshot) -> list[tuple[str, str]]:
    changed = "\n".join(f"- {path}" for path in snapshot.changed_files)
    return [
        ("Branch", snapshot.branch),
        ("Changed Files", changed),
        ("Working Tree Status", snapshot.status_short),
        ("Staged Diff", snapshot.staged_diff),
        ("Unstaged Diff", snapshot.unstaged_diff),
        ("Untracked Files", snapshot.untracked_files),
        ("Recent Commit Subjects", snapshot.recent_commits),
    ]


def _compress_diff_text(text: str, head_lines: int, tail_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= head_lines + tail_lines + 1:
        return text
    kept_head = lines[:head_lines]
    kept_tail = lines[-tail_lines:] if tail_lines > 0 else []
    omitted = len(lines) - len(kept_head) - len(kept_tail)
    marker = [f"...[diff compressed: {omitted} lines omitted]..."]
    return "\n".join(kept_head + marker + kept_tail)


def _build_user_prompt(context: str) -> str:
    return (
        "Generate one normalized conventional commit proposal from the git context.\n"
        "Focus on user-impacting and structural changes, not file-by-file narration.\n\n"
        f"{context}\n"
    )


def _ensure_positive_token_limit(max_tokens: int) -> None:
    if max_tokens <= 0:
        raise ConfigError("max_context_tokens must be a positive integer.")


def build_context(snapshot: RepoSnapshot, max_chars: int) -> str:
    """Create context string within user-defined limit."""
    sections = _build_sections(snapshot)
    return _trim_sections(sections, max_chars=max_chars)


def build_prompt(
    snapshot: RepoSnapshot,
    max_chars: int,
    *,
    max_tokens: int | None = None,
    token_model: str = DEFAULT_TOKEN_MODEL,
    token_encoding: str | None = None,
) -> PromptPayload:
    """Return model prompts with bounded git context and optional token compression."""
    sections = _build_sections(snapshot)
    context = _trim_sections(sections, max_chars=max_chars)

    try:
        counter = create_token_counter(
            model_name=token_model, encoding_name=token_encoding
        )
    except ConfigError as exc:
        if max_tokens is not None or "requires 'tiktoken'" not in str(exc):
            raise
        user_prompt = _build_user_prompt(context)
        return PromptPayload(system=SYSTEM_PROMPT, user=user_prompt, context=context)

    user_prompt = _build_user_prompt(context)
    context_tokens_before = counter.count(context)
    total_tokens_before = counter.count(SYSTEM_PROMPT) + counter.count(user_prompt)

    token_limit = max_tokens
    compression_steps: list[str] = []
    if token_limit is not None:
        _ensure_positive_token_limit(token_limit)
        current_tokens = context_tokens_before
        if current_tokens > token_limit:
            section_map = dict(sections)
            for section_name in ("Untracked Files", "Recent Commit Subjects"):
                if section_map.get(section_name, "").strip():
                    section_map[section_name] = ""
                    compression_steps.append(f"drop_{section_name.lower().replace(' ', '_')}")
            if compression_steps:
                ordered = [(title, section_map.get(title, "")) for title, _ in sections]
                context = _trim_sections(ordered, max_chars=max_chars)
                current_tokens = counter.count(context)

        if current_tokens > token_limit:
            diff_budget = [(120, 40), (80, 24), (40, 12), (20, 6)]
            section_map = dict(sections)
            for section_name in ("Untracked Files", "Recent Commit Subjects"):
                section_map[section_name] = ""

            for head_lines, tail_lines in diff_budget:
                changed_any = False
                for diff_name in ("Staged Diff", "Unstaged Diff"):
                    original = section_map.get(diff_name, "")
                    compressed = _compress_diff_text(original, head_lines, tail_lines)
                    if compressed != original:
                        section_map[diff_name] = compressed
                        changed_any = True
                if not changed_any:
                    continue

                ordered = [(title, section_map.get(title, "")) for title, _ in sections]
                candidate = _trim_sections(ordered, max_chars=max_chars)
                candidate_tokens = counter.count(candidate)
                compression_steps.append(
                    f"compress_diffs_head{head_lines}_tail{tail_lines}"
                )
                context = candidate
                current_tokens = candidate_tokens
                if candidate_tokens <= token_limit:
                    break

        if current_tokens > token_limit:
            context = counter.truncate(context, token_limit)
            compression_steps.append("hard_token_truncate")

    user_prompt = _build_user_prompt(context)
    context_tokens_after = counter.count(context)
    total_tokens_after = counter.count(SYSTEM_PROMPT) + counter.count(user_prompt)
    token_usage = PromptTokenUsage(
        model_name=token_model,
        encoding_name=counter.encoding_name,
        context_tokens_before=context_tokens_before,
        context_tokens_after=context_tokens_after,
        total_tokens_before=total_tokens_before,
        total_tokens_after=total_tokens_after,
        token_limit=token_limit,
        compression_applied=bool(compression_steps),
        compression_steps=tuple(compression_steps),
    )
    return PromptPayload(
        system=SYSTEM_PROMPT,
        user=user_prompt,
        context=context,
        token_usage=token_usage,
    )
