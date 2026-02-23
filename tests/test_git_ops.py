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


if __name__ == "__main__":
    unittest.main()
