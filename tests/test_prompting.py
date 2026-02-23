from __future__ import annotations

import unittest

from lazy_commit.git_ops import RepoSnapshot
from lazy_commit.prompting import build_context


class PromptingTests(unittest.TestCase):
    def test_build_context_trims_to_limit(self) -> None:
        snapshot = RepoSnapshot(
            branch="main",
            status_short="M src/a.py\nM src/b.py",
            staged_diff="x" * 300,
            unstaged_diff="y" * 300,
            untracked_files="",
            changed_files=["src/a.py", "src/b.py"],
            recent_commits="feat: something",
        )
        context = build_context(snapshot, max_chars=180)
        self.assertLessEqual(len(context), 180 + 30)  # includes truncation marker
        self.assertIn("Changed Files", context)


if __name__ == "__main__":
    unittest.main()

