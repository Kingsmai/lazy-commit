from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch

from lazy_commit.cli import run
from lazy_commit.config import Settings
from lazy_commit.errors import ConfigError
from lazy_commit.git_ops import RepoSnapshot
from lazy_commit.i18n import get_language, set_language
from lazy_commit.prompting import PromptPayload, PromptTokenUsage
from lazy_commit.token_count import TokenCountResult


class _Proposal:
    def to_commit_message(self) -> str:
        return "chore(cli): add progress logs\n"


class CLIRunLoggingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_language = get_language()
        set_language("en")
        self._env_patcher = patch.dict(os.environ, {"LAZY_COMMIT_LANG": "en"}, clear=False)
        self._env_patcher.start()

    def tearDown(self) -> None:
        self._env_patcher.stop()
        set_language(self._original_language)

    def _find_line_index(self, lines: list[str], fragment: str) -> int:
        for idx, line in enumerate(lines):
            if fragment in line:
                return idx
        raise AssertionError(f"Missing output line: {fragment!r}")

    def test_run_emits_progress_logs_for_main_generation_flow(self) -> None:
        settings = Settings(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model_name="gpt-4.1-mini",
            max_context_size=12000,
            provider="openai",
        )
        snapshot = RepoSnapshot(
            branch="main",
            status_short="M src/lazy_commit/cli.py",
            staged_diff="",
            unstaged_diff="diff --git a/src/lazy_commit/cli.py b/src/lazy_commit/cli.py",
            untracked_files="",
            changed_files=["src/lazy_commit/cli.py"],
            recent_commits="chore: baseline",
        )
        prompt_payload = PromptPayload(system="system", user="user", context="context")

        with patch("lazy_commit.cli.load_settings", return_value=settings), patch(
            "lazy_commit.cli.GitClient"
        ) as git_client_cls, patch(
            "lazy_commit.cli.build_prompt", return_value=prompt_payload
        ), patch(
            "lazy_commit.cli.LLMClient"
        ) as llm_client_cls, patch(
            "lazy_commit.cli.parse_commit_proposal", return_value=_Proposal()
        ), patch("builtins.print") as mocked_print:
            git_client = git_client_cls.return_value
            git_client.snapshot.return_value = snapshot

            llm_client = llm_client_cls.return_value
            llm_client.complete.return_value.text = (
                '{"type":"chore","scope":"cli","subject":"add progress logs","body":[],"breaking_change":false}'
            )

            exit_code = run(["--no-copy"])

        self.assertEqual(exit_code, 0)

        lines = [str(call.args[0]) for call in mocked_print.call_args_list if call.args]
        loading_idx = self._find_line_index(lines, "Loading settings...")
        repo_idx = self._find_line_index(lines, "Checking git repository...")
        snapshot_idx = self._find_line_index(lines, "Collecting git snapshot...")
        context_idx = self._find_line_index(lines, "Building model context...")
        request_idx = self._find_line_index(lines, "Requesting commit proposal")
        parse_idx = self._find_line_index(lines, "Parsing model response...")

        self.assertLess(loading_idx, repo_idx)
        self.assertLess(repo_idx, snapshot_idx)
        self.assertLess(snapshot_idx, context_idx)
        self.assertLess(context_idx, request_idx)
        self.assertLess(request_idx, parse_idx)

    def test_run_logs_early_steps_when_no_changes(self) -> None:
        settings = Settings(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model_name="gpt-4.1-mini",
            max_context_size=12000,
            provider="openai",
        )
        snapshot = RepoSnapshot(
            branch="main",
            status_short="",
            staged_diff="",
            unstaged_diff="",
            untracked_files="",
            changed_files=[],
            recent_commits="chore: baseline",
        )

        with patch("lazy_commit.cli.load_settings", return_value=settings), patch(
            "lazy_commit.cli.GitClient"
        ) as git_client_cls, patch("builtins.print") as mocked_print:
            git_client = git_client_cls.return_value
            git_client.snapshot.return_value = snapshot

            exit_code = run(["--no-copy"])

        self.assertEqual(exit_code, 0)
        lines = [str(call.args[0]) for call in mocked_print.call_args_list if call.args]
        self._find_line_index(lines, "Loading settings...")
        self._find_line_index(lines, "Checking git repository...")
        self._find_line_index(lines, "Collecting git snapshot...")
        self._find_line_index(lines, "No local changes found. Nothing to generate.")
        self.assertFalse(any("Building model context..." in line for line in lines))

    def test_run_count_tokens_mode_skips_generation_flow(self) -> None:
        token_result = TokenCountResult(
            token_count=7,
            character_count=11,
            model_name="gpt-4.1-mini",
            encoding_name="o200k_base",
        )

        with patch(
            "lazy_commit.cli.count_tokens", return_value=token_result
        ) as count_tokens_mock, patch(
            "lazy_commit.cli.load_settings"
        ) as load_settings_mock, patch(
            "lazy_commit.cli.GitClient"
        ) as git_client_cls, patch("builtins.print") as mocked_print:
            exit_code = run(["--count-tokens", "hello world"])

        self.assertEqual(exit_code, 0)
        count_tokens_mock.assert_called_once_with(
            "hello world",
            model_name="gpt-4.1-mini",
            encoding_name=None,
        )
        load_settings_mock.assert_not_called()
        git_client_cls.assert_not_called()

        lines = [str(call.args[0]) for call in mocked_print.call_args_list if call.args]
        self._find_line_index(lines, "Token Count")
        self._find_line_index(lines, "Characters")
        self._find_line_index(lines, "Tokens")

    def test_run_count_tokens_without_text_requires_piped_stdin(self) -> None:
        fake_stdin = Mock()
        fake_stdin.isatty.return_value = True

        with patch("sys.stdin", fake_stdin):
            with self.assertRaises(ConfigError):
                run(["--count-tokens"])

    def test_run_logs_token_budget_and_compression_when_available(self) -> None:
        settings = Settings(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model_name="gpt-4.1-mini",
            max_context_size=12000,
            provider="openai",
            max_context_tokens=800,
        )
        snapshot = RepoSnapshot(
            branch="main",
            status_short="M src/lazy_commit/cli.py",
            staged_diff="diff --git a/src/lazy_commit/cli.py b/src/lazy_commit/cli.py",
            unstaged_diff="",
            untracked_files="",
            changed_files=["src/lazy_commit/cli.py"],
            recent_commits="chore: baseline",
        )
        usage = PromptTokenUsage(
            model_name="gpt-4.1-mini",
            encoding_name="o200k_base",
            context_tokens_before=1200,
            context_tokens_after=800,
            total_tokens_before=1500,
            total_tokens_after=1100,
            token_limit=800,
            compression_applied=True,
            compression_steps=("drop_untracked_files", "hard_token_truncate"),
        )
        prompt_payload = PromptPayload(
            system="system",
            user="user",
            context="context",
            token_usage=usage,
        )

        with patch("lazy_commit.cli.load_settings", return_value=settings), patch(
            "lazy_commit.cli.GitClient"
        ) as git_client_cls, patch(
            "lazy_commit.cli.build_prompt", return_value=prompt_payload
        ), patch(
            "lazy_commit.cli.LLMClient"
        ) as llm_client_cls, patch(
            "lazy_commit.cli.parse_commit_proposal", return_value=_Proposal()
        ), patch("builtins.print") as mocked_print:
            git_client = git_client_cls.return_value
            git_client.snapshot.return_value = snapshot

            llm_client = llm_client_cls.return_value
            llm_client.complete.return_value.text = (
                '{"type":"chore","scope":"cli","subject":"add progress logs","body":[],"breaking_change":false}'
            )

            exit_code = run(["--no-copy"])

        self.assertEqual(exit_code, 0)
        lines = [str(call.args[0]) for call in mocked_print.call_args_list if call.args]
        self._find_line_index(lines, "Estimated prompt tokens:")
        self._find_line_index(lines, "Context token budget:")
        self._find_line_index(lines, "compression applied")

    def test_run_supports_chinese_logs_with_lang_flag(self) -> None:
        settings = Settings(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model_name="gpt-4.1-mini",
            max_context_size=12000,
            provider="openai",
        )
        snapshot = RepoSnapshot(
            branch="main",
            status_short="",
            staged_diff="",
            unstaged_diff="",
            untracked_files="",
            changed_files=[],
            recent_commits="chore: baseline",
        )

        with patch("lazy_commit.cli.load_settings", return_value=settings), patch(
            "lazy_commit.cli.GitClient"
        ) as git_client_cls, patch("builtins.print") as mocked_print:
            git_client = git_client_cls.return_value
            git_client.snapshot.return_value = snapshot

            exit_code = run(["--lang", "zh-CN", "--no-copy"])

        self.assertEqual(exit_code, 0)
        lines = [str(call.args[0]) for call in mocked_print.call_args_list if call.args]
        self._find_line_index(lines, "正在加载配置...")
        self._find_line_index(lines, "正在检查 Git 仓库...")
        self._find_line_index(lines, "未发现本地变更，无需生成提交信息。")


if __name__ == "__main__":
    unittest.main()
