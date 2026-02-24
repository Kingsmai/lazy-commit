from __future__ import annotations

import unittest
from unittest.mock import patch

from lazy_commit.errors import ConfigError
from lazy_commit.git_ops import RepoSnapshot
from lazy_commit.prompting import build_context, build_prompt


class _FakeCounter:
    def __init__(self) -> None:
        self.encoding_name = "fake-encoding"

    def count(self, text: str) -> int:
        return len(text)

    def truncate(self, text: str, max_tokens: int) -> str:
        return text[:max_tokens]


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

    def test_build_prompt_reports_token_usage(self) -> None:
        snapshot = RepoSnapshot(
            branch="main",
            status_short="M src/a.py",
            staged_diff="diff --git a/src/a.py b/src/a.py\n+print('x')",
            unstaged_diff="",
            untracked_files="tmp.txt",
            changed_files=["src/a.py"],
            recent_commits="feat: baseline",
        )
        with patch("lazy_commit.prompting.create_token_counter", return_value=_FakeCounter()):
            payload = build_prompt(
                snapshot,
                max_chars=4000,
                token_model="gpt-4.1-mini",
            )
        usage = payload.token_usage
        self.assertIsNotNone(usage)
        if usage is None:
            self.fail("token usage should be available")
        self.assertEqual(usage.encoding_name, "fake-encoding")
        self.assertFalse(usage.compression_applied)

    def test_build_prompt_compresses_when_token_limit_exceeded(self) -> None:
        snapshot = RepoSnapshot(
            branch="main",
            status_short="M src/a.py\nM src/b.py",
            staged_diff="\n".join([f"+ staged line {i}" for i in range(220)]),
            unstaged_diff="\n".join([f"+ unstaged line {i}" for i in range(220)]),
            untracked_files="\n".join([f"tmp/file_{i}.txt" for i in range(80)]),
            changed_files=["src/a.py", "src/b.py"],
            recent_commits="\n".join([f"feat: message {i}" for i in range(40)]),
        )
        with patch("lazy_commit.prompting.create_token_counter", return_value=_FakeCounter()):
            payload = build_prompt(
                snapshot,
                max_chars=50000,
                max_tokens=500,
                token_model="gpt-4.1-mini",
            )
        usage = payload.token_usage
        self.assertIsNotNone(usage)
        if usage is None:
            self.fail("token usage should be available")
        self.assertTrue(usage.compression_applied)
        self.assertLessEqual(usage.context_tokens_after, 500)
        self.assertNotIn("## Untracked Files", payload.context)

    def test_build_prompt_rejects_non_positive_token_limit(self) -> None:
        snapshot = RepoSnapshot(
            branch="main",
            status_short="M src/a.py",
            staged_diff="+line",
            unstaged_diff="",
            untracked_files="",
            changed_files=["src/a.py"],
            recent_commits="chore: baseline",
        )
        with patch("lazy_commit.prompting.create_token_counter", return_value=_FakeCounter()):
            with self.assertRaises(ConfigError):
                build_prompt(
                    snapshot,
                    max_chars=1000,
                    max_tokens=0,
                    token_model="gpt-4.1-mini",
                )


if __name__ == "__main__":
    unittest.main()
