"""Persist and query generated commit history."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

DEFAULT_HISTORY_LIMIT = 20
_FALLBACK_MIN_DATETIME = datetime.min.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class HistoryEntry:
    """One generated commit proposal stored in local history."""

    generated_at: str
    project_name: str
    repo_path: str
    branch: str
    commit_message: str
    changed_files: tuple[str, ...]
    provider: str | None = None
    model_name: str | None = None

    @property
    def subject(self) -> str:
        lines = self.commit_message.splitlines()
        return lines[0] if lines else ""


def history_path() -> Path:
    """Resolve the on-disk history location."""
    override = (os.getenv("LAZY_COMMIT_HISTORY_PATH") or "").strip()
    if override:
        return Path(override).expanduser()

    xdg_state_home = (os.getenv("XDG_STATE_HOME") or "").strip()
    if xdg_state_home:
        return Path(xdg_state_home).expanduser() / "lazy-commit" / "history.jsonl"

    if os.name == "nt":
        local_app_data = (os.getenv("LOCALAPPDATA") or "").strip()
        if local_app_data:
            return Path(local_app_data).expanduser() / "lazy-commit" / "history.jsonl"

    return Path.home() / ".local" / "state" / "lazy-commit" / "history.jsonl"


def _normalize_repo_path(repo_path: str | Path) -> str:
    raw_value = str(repo_path).strip()
    if not raw_value:
        return str(Path.cwd())
    normalized = Path(raw_value).expanduser()
    if not normalized.is_absolute():
        normalized = (Path.cwd() / normalized).resolve()
    return str(normalized)


def build_history_entry(
    *,
    repo_path: str | Path,
    branch: str,
    commit_message: str,
    changed_files: Sequence[str],
    provider: str | None = None,
    model_name: str | None = None,
    generated_at: str | None = None,
) -> HistoryEntry:
    """Build a normalized history entry for persistence."""
    normalized_repo_path = _normalize_repo_path(repo_path)
    project_name = Path(normalized_repo_path).name or normalized_repo_path
    normalized_message = commit_message.rstrip("\n")
    return HistoryEntry(
        generated_at=generated_at
        or datetime.now().astimezone().isoformat(timespec="seconds"),
        project_name=project_name,
        repo_path=normalized_repo_path,
        branch=branch,
        commit_message=normalized_message,
        changed_files=tuple(str(path) for path in changed_files),
        provider=provider,
        model_name=model_name,
    )


def record_history_entry(entry: HistoryEntry, path: Path | None = None) -> Path:
    """Append one entry to the history file."""
    history_file = path or history_path()
    history_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": entry.generated_at,
        "project_name": entry.project_name,
        "repo_path": entry.repo_path,
        "branch": entry.branch,
        "commit_message": entry.commit_message,
        "changed_files": list(entry.changed_files),
        "provider": entry.provider,
        "model_name": entry.model_name,
    }
    with history_file.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return history_file


def _parse_history_entry(payload: object) -> HistoryEntry | None:
    if not isinstance(payload, dict):
        return None

    generated_at = payload.get("generated_at")
    project_name = payload.get("project_name")
    repo_path = payload.get("repo_path")
    branch = payload.get("branch")
    commit_message = payload.get("commit_message")
    changed_files = payload.get("changed_files")
    provider = payload.get("provider")
    model_name = payload.get("model_name")

    if not all(isinstance(value, str) and value.strip() for value in (
        generated_at,
        project_name,
        repo_path,
        branch,
        commit_message,
    )):
        return None

    normalized_changed_files: tuple[str, ...]
    if isinstance(changed_files, list):
        normalized_changed_files = tuple(
            item for item in changed_files if isinstance(item, str) and item.strip()
        )
    else:
        normalized_changed_files = ()

    return HistoryEntry(
        generated_at=generated_at,
        project_name=project_name,
        repo_path=repo_path,
        branch=branch,
        commit_message=commit_message,
        changed_files=normalized_changed_files,
        provider=provider if isinstance(provider, str) and provider else None,
        model_name=model_name if isinstance(model_name, str) and model_name else None,
    )


def _parse_generated_at(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return _FALLBACK_MIN_DATETIME
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def format_history_timestamp(value: str) -> str:
    """Format an ISO timestamp for terminal display."""
    parsed = _parse_generated_at(value)
    if parsed == _FALLBACK_MIN_DATETIME:
        return value
    return parsed.isoformat(sep=" ", timespec="seconds")


def _matches_query(entry: HistoryEntry, query: str | None) -> bool:
    if not query:
        return True
    tokens = [token.casefold() for token in query.split() if token.strip()]
    if not tokens:
        return True
    haystack = "\n".join(
        (
            entry.project_name,
            entry.repo_path,
            entry.branch,
            entry.commit_message,
            *entry.changed_files,
        )
    ).casefold()
    return all(token in haystack for token in tokens)


def load_history_entries(
    *,
    query: str | None = None,
    limit: int = DEFAULT_HISTORY_LIMIT,
    path: Path | None = None,
) -> list[HistoryEntry]:
    """Load recent history entries, optionally filtered by query."""
    if limit <= 0:
        raise ValueError("limit must be a positive integer.")

    history_file = path or history_path()
    if not history_file.exists():
        return []

    entries: list[HistoryEntry] = []
    with history_file.open("r", encoding="utf-8") as stream:
        for line in stream:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            entry = _parse_history_entry(payload)
            if entry is None or not _matches_query(entry, query):
                continue
            entries.append(entry)

    entries.sort(key=lambda item: _parse_generated_at(item.generated_at), reverse=True)
    return entries[:limit]
