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


@dataclass(frozen=True)
class FileChange:
    """One changed file from `git status --porcelain`."""

    index_status: str
    worktree_status: str
    path: str
    original_path: str | None = None

    @property
    def status_code(self) -> str:
        return f"{self.index_status}{self.worktree_status}"

    @property
    def is_staged(self) -> bool:
        return self.index_status not in {" ", "?"}

    @property
    def is_untracked(self) -> bool:
        return self.index_status == "?" and self.worktree_status == "?"


def _parse_porcelain_changes(output: str) -> list[FileChange]:
    changes: list[FileChange] = []
    for line in output.splitlines():
        if not line.strip() or len(line) < 4:
            continue

        index_status = line[0]
        worktree_status = line[1]
        path = line[3:]
        original_path: str | None = None
        if " -> " in path:
            original_path, path = path.split(" -> ", maxsplit=1)

        changes.append(
            FileChange(
                index_status=index_status,
                worktree_status=worktree_status,
                path=path,
                original_path=original_path,
            )
        )
    return changes


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

    def repo_root(self) -> str:
        result = self._run("rev-parse", "--show-toplevel")
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
        files = [change.path for change in _parse_porcelain_changes(result.stdout or "")]
        seen: set[str] = set()
        deduped: list[str] = []
        for item in files:
            if item not in seen:
                seen.add(item)
                deduped.append(item)
        return deduped

    def file_changes(self) -> list[FileChange]:
        result = self._run("status", "--porcelain")
        return _parse_porcelain_changes((result.stdout or "").rstrip())

    def recent_commit_subjects(self, limit: int = 5) -> str:
        result = self._run("log", f"-{limit}", "--pretty=format:%s", check=False)
        if result.returncode != 0:
            return ""
        return (result.stdout or "").rstrip()

    def stage_all(self) -> None:
        self._run("add", "--all")

    def stage_file(self, path: str) -> None:
        self._run("add", "--", path)

    def unstage_file(self, path: str) -> None:
        restore = self._run("restore", "--staged", "--", path, check=False)
        if restore.returncode == 0:
            return

        reset = self._run("reset", "HEAD", "--", path, check=False)
        if reset.returncode == 0:
            return

        rm_cached = self._run("rm", "--cached", "--", path, check=False)
        if rm_cached.returncode == 0:
            return

        stderr = (
            (restore.stderr or "").strip()
            or (reset.stderr or "").strip()
            or (rm_cached.stderr or "").strip()
            or (restore.stdout or "").strip()
            or (reset.stdout or "").strip()
            or (rm_cached.stdout or "").strip()
        )
        raise GitError(f"git unstage {path} failed: {stderr}")

    def commit(self, message: str) -> str:
        result = self._run("commit", "-F", "-", input_text=message)
        return (result.stdout or "").strip()

    def push(self, remote: str, branch: str) -> str:
        result = self._run("push", remote, branch)
        return ((result.stdout or "") + (result.stderr or "")).strip()

    def diff_for_file(self, path: str) -> str:
        staged = self._run(
            "diff", "--cached", "--no-color", "--unified=3", "--", path
        )
        unstaged = self._run("diff", "--no-color", "--unified=3", "--", path)

        sections: list[str] = []
        staged_text = (staged.stdout or "").rstrip()
        unstaged_text = (unstaged.stdout or "").rstrip()
        if staged_text:
            sections.append(f"## Staged\n{staged_text}")
        if unstaged_text:
            sections.append(f"## Unstaged\n{unstaged_text}")
        if sections:
            return "\n\n".join(sections)

        return self._read_untracked_preview(path)

    def _read_untracked_preview(
        self,
        path: str,
        *,
        max_lines: int = 200,
        max_chars: int = 20000,
    ) -> str:
        candidate = (self.cwd / path).resolve()
        if not candidate.exists():
            return f"No diff available for {path}."

        try:
            raw = candidate.read_bytes()
        except OSError as exc:
            return f"Unable to read {path}: {exc}"

        if b"\x00" in raw[:4096]:
            return f"Untracked binary file: {path}"

        text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines()
        truncated = False
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            truncated = True

        preview = "\n".join(lines)
        if len(preview) > max_chars:
            preview = preview[:max_chars]
            truncated = True

        if truncated:
            preview = preview.rstrip() + "\n...[preview truncated]"

        header = f"## Untracked file preview\n{path}"
        if not preview.strip():
            return f"{header}\n\n(empty file)"
        return f"{header}\n\n{preview}"

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
