"""Shared workflow helpers for CLI and TUI execution paths."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, replace
from typing import Callable

from .commit_message import parse_commit_proposal
from .config import Settings
from .errors import GitError
from .git_ops import GitClient, RepoSnapshot
from .history import HistoryEntry, build_history_entry, record_history_entry
from .i18n import t
from .llm import LLMClient
from .prompting import PromptPayload, build_prompt

_INTERRUPT_POLL_SECONDS = 0.1


@dataclass(frozen=True)
class GenerationResult:
    """One generated commit proposal after LLM parsing/normalization."""

    raw_response: str
    final_message: str


@dataclass(frozen=True)
class ApplyResult:
    """Outputs captured from commit/push execution."""

    commit_output: str
    push_output: str | None = None
    branch: str | None = None


def build_generation_payload(
    settings: Settings,
    snapshot: RepoSnapshot,
    *,
    token_model: str | None = None,
    token_encoding: str | None = None,
) -> PromptPayload:
    """Build the bounded prompt payload for one repository snapshot."""
    prompt_token_model = token_model or settings.model_name
    return build_prompt(
        snapshot,
        max_chars=settings.max_context_size,
        max_tokens=settings.max_context_tokens,
        token_model=prompt_token_model,
        token_encoding=token_encoding,
    )


def finalize_generation(
    raw_response: str,
    *,
    wip: bool = False,
) -> GenerationResult:
    """Normalize one raw model response into a final commit message."""
    proposal = parse_commit_proposal(raw_response)
    if wip:
        proposal = replace(proposal, commit_type="wip")
    return GenerationResult(
        raw_response=raw_response,
        final_message=proposal.to_commit_message(),
    )


def request_commit_proposal(
    settings: Settings,
    prompt_payload: PromptPayload,
    *,
    client: LLMClient | None = None,
) -> str:
    """Request a raw commit proposal string from the configured model."""
    llm_client = client or LLMClient(settings)
    return _run_interruptibly(lambda: llm_client.complete(prompt_payload).text)


def _run_interruptibly(operation: Callable[[], str]) -> str:
    result_queue: queue.Queue[tuple[str, str | BaseException]] = queue.Queue(maxsize=1)

    def _worker() -> None:
        try:
            result_queue.put(("value", operation()))
        except BaseException as exc:
            result_queue.put(("error", exc))

    worker = threading.Thread(
        target=_worker,
        name="lazy-commit-llm-request",
        daemon=True,
    )
    worker.start()

    while True:
        try:
            kind, payload = result_queue.get(timeout=_INTERRUPT_POLL_SECONDS)
        except queue.Empty:
            if worker.is_alive():
                continue
            raise RuntimeError("LLM request worker exited without a result.")

        if kind == "error":
            assert isinstance(payload, BaseException)
            raise payload
        assert isinstance(payload, str)
        return payload


def record_generated_history(
    git: GitClient,
    snapshot: RepoSnapshot,
    final_message: str,
    settings: Settings,
) -> HistoryEntry:
    """Persist one generated message to history."""
    entry = build_history_entry(
        repo_path=git.repo_root(),
        branch=snapshot.branch,
        commit_message=final_message,
        changed_files=snapshot.changed_files,
        provider=settings.provider,
        model_name=settings.model_name,
    )
    record_history_entry(entry)
    return entry


def apply_commit_message(
    git: GitClient,
    message: str,
    *,
    stage_all: bool = False,
    push: bool = False,
    remote: str = "origin",
    branch: str | None = None,
) -> ApplyResult:
    """Apply a generated commit message, optionally staging and pushing."""
    if stage_all:
        git.stage_all()

    if not git.snapshot().has_staged_changes:
        raise GitError(t("cli.error.no_staged_changes"))

    commit_output = git.commit(message)
    if not push:
        return ApplyResult(commit_output=commit_output)

    resolved_branch = branch or git.current_branch()
    push_output = git.push(remote, resolved_branch)
    return ApplyResult(
        commit_output=commit_output,
        push_output=push_output,
        branch=resolved_branch,
    )
