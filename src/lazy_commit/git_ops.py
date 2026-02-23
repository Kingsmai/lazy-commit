"""Git helpers for collecting context and applying commits."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .errors import GitError


@dataclass(frozen=True)
class RepoSnapshot:
    """Git information used for prompt/context rendering."""

    branch: str
    status_short: str
    staged_diff: str
    unstaged_diff: str
    untracked_files: str
    changed_files: list[str]
    recent_commits: str

    @property
    def has_any_changes(self) -> bool:
        return bool(self.status_short.strip())

    @property
    def has_staged_changes(self) -> bool:
        return bool(self.staged_diff.strip())


class GitClient:
    """Thin wrapper around subprocess git commands."""

    def __init__(self, cwd: Path | str | None = None) -> None:
        self.cwd = Path(cwd or ".").resolve()

    def _run(
        self,
        *args: str,
        check: bool = True,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            ["git", *args],
            cwd=self.cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            input=input_text,
            capture_output=True,
            check=False,
        )
        if check and completed.returncode != 0:
            stderr = (completed.stderr or "").strip() or (completed.stdout or "").strip()
            raise GitError(f"git {' '.join(args)} failed: {stderr}")
        return completed

    def ensure_repo(self) -> None:
        result = self._run("rev-parse", "--is-inside-work-tree")
        if (result.stdout or "").strip().lower() != "true":
            raise GitError(f"{self.cwd} is not inside a git repository.")

    def current_branch(self) -> str:
        result = self._run("rev-parse", "--abbrev-ref", "HEAD")
        return (result.stdout or "").strip()

    def status_short(self) -> str:
        result = self._run("status", "--short")
        return (result.stdout or "").rstrip()

    def staged_diff(self) -> str:
        result = self._run("diff", "--cached", "--no-color", "--unified=3")
        return (result.stdout or "").rstrip()

    def unstaged_diff(self) -> str:
        result = self._run("diff", "--no-color", "--unified=3")
        return (result.stdout or "").rstrip()

    def untracked_files(self) -> str:
        result = self._run("ls-files", "--others", "--exclude-standard")
        return (result.stdout or "").rstrip()

    def changed_files(self) -> list[str]:
        result = self._run("status", "--porcelain")
        lines = [
            line.strip()
            for line in (result.stdout or "").splitlines()
            if line.strip()
        ]
        files: list[str] = []
        for line in lines:
            if len(line) < 4:
                continue
            path = line[3:]
            # For renames git returns "old -> new"; keep destination.
            if " -> " in path:
                path = path.split(" -> ", maxsplit=1)[1]
            files.append(path)
        seen: set[str] = set()
        deduped: list[str] = []
        for item in files:
            if item not in seen:
                seen.add(item)
                deduped.append(item)
        return deduped

    def recent_commit_subjects(self, limit: int = 5) -> str:
        result = self._run("log", f"-{limit}", "--pretty=format:%s", check=False)
        if result.returncode != 0:
            return ""
        return (result.stdout or "").rstrip()

    def stage_all(self) -> None:
        self._run("add", "--all")

    def commit(self, message: str) -> str:
        result = self._run("commit", "-F", "-", input_text=message)
        return (result.stdout or "").strip()

    def push(self, remote: str, branch: str) -> str:
        result = self._run("push", remote, branch)
        return ((result.stdout or "") + (result.stderr or "")).strip()

    def snapshot(self) -> RepoSnapshot:
        return RepoSnapshot(
            branch=self.current_branch(),
            status_short=self.status_short(),
            staged_diff=self.staged_diff(),
            unstaged_diff=self.unstaged_diff(),
            untracked_files=self.untracked_files(),
            changed_files=self.changed_files(),
            recent_commits=self.recent_commit_subjects(),
        )
