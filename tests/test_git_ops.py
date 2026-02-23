from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()

