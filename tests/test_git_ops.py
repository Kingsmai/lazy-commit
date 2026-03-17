from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from lazy_commit.git_ops import GitClient, RepoSnapshot


class GitOpsTests(unittest.TestCase):
    def test_commit_scope_uses_only_staged_context_when_available(self) -> None:
        snapshot = RepoSnapshot(
            branch="main",
            status_short="\n".join(
                [
                    "M  src/staged.py",
                    " M src/unstaged.py",
                    "MM src/mixed.py",
                    "?? tmp/new.txt",
                ]
            ),
            staged_diff="diff --git a/src/staged.py b/src/staged.py\n+staged",
            unstaged_diff="diff --git a/src/unstaged.py b/src/unstaged.py\n+unstaged",
            untracked_files="tmp/new.txt",
            changed_files=[
                "src/staged.py",
                "src/unstaged.py",
                "src/mixed.py",
                "tmp/new.txt",
            ],
            recent_commits="chore: baseline",
        )

        scoped = snapshot.commit_scope()

        self.assertEqual(scoped.changed_files, ["src/staged.py", "src/mixed.py"])
        self.assertEqual(scoped.unstaged_diff, "")
        self.assertEqual(scoped.untracked_files, "")
        self.assertEqual(scoped.status_short, "M  src/staged.py\nM  src/mixed.py")

    def test_commit_scope_keeps_full_context_when_stage_all_is_requested(self) -> None:
        snapshot = RepoSnapshot(
            branch="main",
            status_short="M  src/staged.py\n M src/unstaged.py",
            staged_diff="diff --git a/src/staged.py b/src/staged.py\n+staged",
            unstaged_diff="diff --git a/src/unstaged.py b/src/unstaged.py\n+unstaged",
            untracked_files="",
            changed_files=["src/staged.py", "src/unstaged.py"],
            recent_commits="chore: baseline",
        )

        scoped = snapshot.commit_scope(stage_all=True)

        self.assertIs(scoped, snapshot)

    def test_snapshot_handles_none_stdout_without_crashing(self) -> None:
        client = GitClient(cwd=".")

        with patch.object(client, "current_branch", return_value="main"), patch.object(
            client, "status_short", return_value=""
        ), patch.object(client, "staged_diff", return_value=""), patch.object(
            client, "unstaged_diff", return_value=""
        ), patch.object(
            client, "untracked_files", return_value=""
        ), patch.object(
            client, "changed_files", return_value=[]
        ), patch.object(
            client, "recent_commit_subjects", return_value=""
        ):
            snapshot = client.snapshot()

        self.assertEqual(snapshot.branch, "main")
        self.assertFalse(snapshot.has_any_changes)
        self.assertEqual(snapshot.changed_files, [])

    def test_changed_files_keeps_first_character_for_space_prefixed_status(self) -> None:
        client = GitClient(cwd=".")
        porcelain = "\n".join(
            [
                " M README.md",
                "A  pyproject.toml",
                "?? src/lazy_commit/ui.py",
            ]
        )
        completed = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=0,
            stdout=porcelain,
            stderr="",
        )

        with patch.object(client, "_run", return_value=completed):
            files = client.changed_files()

        self.assertEqual(
            files,
            [
                "README.md",
                "pyproject.toml",
                "src/lazy_commit/ui.py",
            ],
        )

    def test_changed_files_uses_rename_destination(self) -> None:
        client = GitClient(cwd=".")
        completed = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=0,
            stdout="R  old_name.py -> new_name.py",
            stderr="",
        )

        with patch.object(client, "_run", return_value=completed):
            files = client.changed_files()

        self.assertEqual(files, ["new_name.py"])

    def test_file_changes_preserve_status_columns_and_original_path(self) -> None:
        client = GitClient(cwd=".")
        completed = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain"],
            returncode=0,
            stdout="\n".join(
                [
                    "M  README.md",
                    "R  old_name.py -> new_name.py",
                    "?? src/lazy_commit/tui.py",
                ]
            ),
            stderr="",
        )

        with patch.object(client, "_run", return_value=completed):
            changes = client.file_changes()

        self.assertEqual(changes[0].status_code, "M ")
        self.assertTrue(changes[0].is_staged)
        self.assertEqual(changes[1].original_path, "old_name.py")
        self.assertEqual(changes[1].path, "new_name.py")
        self.assertTrue(changes[2].is_untracked)

    def test_diff_for_file_combines_staged_and_unstaged_sections(self) -> None:
        client = GitClient(cwd=".")
        responses = [
            subprocess.CompletedProcess(
                args=["git", "diff", "--cached"],
                returncode=0,
                stdout="diff --git a/file.py b/file.py\n+staged",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["git", "diff"],
                returncode=0,
                stdout="diff --git a/file.py b/file.py\n+unstaged",
                stderr="",
            ),
        ]

        with patch.object(client, "_run", side_effect=responses):
            rendered = client.diff_for_file("file.py")

        self.assertIn("## Staged", rendered)
        self.assertIn("+staged", rendered)
        self.assertIn("## Unstaged", rendered)
        self.assertIn("+unstaged", rendered)

    def test_diff_for_file_uses_untracked_preview_when_git_diff_is_empty(self) -> None:
        client = GitClient(cwd=".")
        responses = [
            subprocess.CompletedProcess(
                args=["git", "diff", "--cached"],
                returncode=0,
                stdout="",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["git", "diff"],
                returncode=0,
                stdout="",
                stderr="",
            ),
        ]

        with patch.object(client, "_run", side_effect=responses), patch.object(
            client,
            "_read_untracked_preview",
            return_value="## Untracked file preview\nfile.py",
        ) as preview_mock:
            rendered = client.diff_for_file("file.py")

        preview_mock.assert_called_once_with("file.py")
        self.assertEqual(rendered, "## Untracked file preview\nfile.py")

    def test_snapshot_has_any_changes_when_only_staged_diff_exists(self) -> None:
        snapshot = RepoSnapshot(
            branch="main",
            status_short="",
            staged_diff="diff --git a/src/app.py b/src/app.py\n+line",
            unstaged_diff="",
            untracked_files="",
            changed_files=[],
            recent_commits="",
        )

        self.assertTrue(snapshot.has_any_changes)


if __name__ == "__main__":
    unittest.main()
