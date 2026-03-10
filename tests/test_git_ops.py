from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from lazy_commit.git_ops import GitClient


class GitOpsTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
