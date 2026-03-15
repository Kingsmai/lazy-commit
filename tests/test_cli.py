from __future__ import annotations

import io
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from lazy_commit.cli import main, run
from lazy_commit.config import Settings
from lazy_commit.errors import ConfigError, LLMError
from lazy_commit.git_ops import RepoSnapshot
from lazy_commit.history import HistoryEntry
from lazy_commit.i18n import LanguageInfo, get_language, set_language
from lazy_commit.prompting import PromptPayload, PromptTokenUsage
from lazy_commit.token_count import TokenCountResult
from lazy_commit.workflow import ApplyResult, GenerationResult


def _generation_result(
    message: str = "chore(cli): add progress logs\n",
    raw_response: str = (
        '{"type":"chore","scope":"cli","subject":"add progress logs","body":[],"breaking_change":false}'
    ),
) -> GenerationResult:
    return GenerationResult(raw_response=raw_response, final_message=message)


class CLIRunLoggingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_language = get_language()
        set_language("en")
        self._history_dir = tempfile.TemporaryDirectory()
        self._env_patcher = patch.dict(
            os.environ,
            {
                "LAZY_COMMIT_LANG": "en",
                "LAZY_COMMIT_HISTORY_PATH": os.path.join(
                    self._history_dir.name, "history.jsonl"
                ),
            },
            clear=False,
        )
        self._env_patcher.start()

    def tearDown(self) -> None:
        self._env_patcher.stop()
        self._history_dir.cleanup()
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
            "lazy_commit.cli.build_generation_payload", return_value=prompt_payload
        ), patch(
            "lazy_commit.cli.request_commit_proposal",
            return_value='{"type":"chore","scope":"cli","subject":"add progress logs","body":[],"breaking_change":false}',
        ), patch(
            "lazy_commit.cli.finalize_generation",
            return_value=_generation_result(),
        ), patch("builtins.print") as mocked_print:
            git_client = git_client_cls.return_value
            git_client.snapshot.return_value = snapshot

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

    def test_run_history_mode_skips_generation_flow(self) -> None:
        entries = [
            HistoryEntry(
                generated_at="2026-03-10T12:34:56+08:00",
                project_name="lazy-commit",
                repo_path="/tmp/lazy-commit",
                branch="main",
                commit_message="feat(cli): add history browser",
                changed_files=("src/lazy_commit/cli.py",),
            )
        ]

        with patch("lazy_commit.cli.load_history_entries", return_value=entries) as load_history_mock, patch(
            "lazy_commit.cli._history_browser_enabled", return_value=False
        ), patch(
            "lazy_commit.cli.load_settings"
        ) as load_settings_mock, patch(
            "lazy_commit.cli.GitClient"
        ) as git_client_cls, patch(
            "lazy_commit.ui.render_history", return_value="history rows"
        ), patch("builtins.print") as mocked_print:
            exit_code = run(["--history", "lazy"])

        self.assertEqual(exit_code, 0)
        load_history_mock.assert_called_once_with(query="lazy", limit=20)
        load_settings_mock.assert_not_called()
        git_client_cls.assert_not_called()

        lines = [str(call.args[0]) for call in mocked_print.call_args_list if call.args]
        self._find_line_index(lines, "Commit History")
        self._find_line_index(lines, "Query")
        self._find_line_index(lines, "Entries")
        self._find_line_index(lines, "history rows")

    def test_run_history_browser_supports_view_and_copy(self) -> None:
        entries = [
            HistoryEntry(
                generated_at="2026-03-10T12:34:56+08:00",
                project_name="lazy-commit",
                repo_path="/tmp/lazy-commit",
                branch="main",
                commit_message="feat(cli): add history browser\n\nshow entry details",
                changed_files=("src/lazy_commit/cli.py",),
                provider="openai",
                model_name="gpt-4.1-mini",
            )
        ]

        with patch("lazy_commit.cli.load_history_entries", return_value=entries), patch(
            "lazy_commit.cli._history_browser_enabled", return_value=True
        ), patch(
            "lazy_commit.ui.render_history", return_value="history rows"
        ), patch(
            "lazy_commit.ui.render_history_detail", return_value="detail rows"
        ) as render_detail_mock, patch(
            "lazy_commit.cli.copy_text"
        ) as copy_text_mock, patch(
            "builtins.input", side_effect=["1", "c 1", "q"]
        ), patch("builtins.print") as mocked_print:
            copy_text_mock.return_value.ok = True
            copy_text_mock.return_value.detail = "Copied to clipboard via clip."

            exit_code = run(["--history"])

        self.assertEqual(exit_code, 0)
        render_detail_mock.assert_called_once_with(entries[0])
        copy_text_mock.assert_called_once_with(
            "feat(cli): add history browser\n\nshow entry details"
        )

        lines = [str(call.args[0]) for call in mocked_print.call_args_list if call.args]
        self._find_line_index(lines, "History browser: enter a number to view details")
        self._find_line_index(lines, "detail rows")
        self._find_line_index(lines, "Copied to clipboard via clip.")

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

    def test_run_tui_launches_full_screen_app(self) -> None:
        settings = Settings(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model_name="gpt-4.1-mini",
            max_context_size=12000,
            provider="openai",
        )
        fake_stdin = Mock()
        fake_stdout = Mock()
        fake_stdin.isatty.return_value = True
        fake_stdout.isatty.return_value = True

        with patch("lazy_commit.cli.load_settings", return_value=settings) as load_settings_mock, patch(
            "lazy_commit.tui.run_tui", return_value=0
        ) as run_tui_mock, patch(
            "sys.stdin", fake_stdin
        ), patch(
            "sys.stdout", fake_stdout
        ):
            exit_code = run(
                [
                    "--tui",
                    "--no-copy",
                    "--wip",
                    "--remote",
                    "upstream",
                    "--branch",
                    "release/main",
                ]
            )

        self.assertEqual(exit_code, 0)
        load_settings_mock.assert_called_once()
        run_tui_mock.assert_called_once()
        self.assertEqual(run_tui_mock.call_args.args[0], settings)
        options = run_tui_mock.call_args.args[1]
        self.assertEqual(options.remote, "upstream")
        self.assertEqual(options.branch, "release/main")
        self.assertFalse(options.copy)
        self.assertTrue(options.wip)

    def test_run_tui_rejects_non_interactive_flags(self) -> None:
        fake_stdin = Mock()
        fake_stdout = Mock()
        fake_stdin.isatty.return_value = True
        fake_stdout.isatty.return_value = True

        with patch("sys.stdin", fake_stdin), patch("sys.stdout", fake_stdout):
            with self.assertRaises(ConfigError) as context:
                run(["--tui", "--apply"])

        self.assertIn("--tui cannot be combined", str(context.exception))

    def test_run_wip_mode_uses_model_generation_and_forces_wip_type(self) -> None:
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

        with patch("lazy_commit.cli.load_settings", return_value=settings) as load_settings_mock, patch(
            "lazy_commit.cli.GitClient"
        ) as git_client_cls, patch(
            "lazy_commit.cli.build_generation_payload", return_value=prompt_payload
        ) as build_prompt_mock, patch(
            "lazy_commit.cli.request_commit_proposal",
            return_value='{"type":"feat","scope":"cli","subject":"checkpoint parser update","body":[],"breaking_change":false}',
        ), patch(
            "lazy_commit.cli.finalize_generation",
            return_value=_generation_result("wip(cli): checkpoint parser update\n"),
        ) as finalize_mock, patch("builtins.print") as mocked_print:
            git_client = git_client_cls.return_value
            git_client.snapshot.return_value = snapshot

            exit_code = run(["--wip", "--no-copy"])

        self.assertEqual(exit_code, 0)
        load_settings_mock.assert_called_once()
        build_prompt_mock.assert_called_once()
        finalize_mock.assert_called_once_with(
            '{"type":"feat","scope":"cli","subject":"checkpoint parser update","body":[],"breaking_change":false}',
            wip=True,
        )

        lines = [str(call.args[0]) for call in mocked_print.call_args_list if call.args]
        self._find_line_index(lines, "Loading settings...")
        self._find_line_index(lines, "WIP mode enabled; forcing generated commit type to wip.")
        self._find_line_index(lines, "wip(cli): checkpoint parser update")

    def test_run_wip_mode_apply_creates_commit(self) -> None:
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
            staged_diff="diff --git a/src/lazy_commit/cli.py b/src/lazy_commit/cli.py",
            unstaged_diff="",
            untracked_files="",
            changed_files=["src/lazy_commit/cli.py"],
            recent_commits="chore: baseline",
        )
        prompt_payload = PromptPayload(system="system", user="user", context="context")

        with patch("lazy_commit.cli.load_settings", return_value=settings) as load_settings_mock, patch(
            "lazy_commit.cli.GitClient"
        ) as git_client_cls, patch(
            "lazy_commit.cli.build_generation_payload", return_value=prompt_payload
        ) as build_prompt_mock, patch(
            "lazy_commit.cli.request_commit_proposal",
            return_value='{"type":"fix","scope":"","subject":"checkpoint before merge","body":[],"breaking_change":false}',
        ), patch(
            "lazy_commit.cli.finalize_generation",
            return_value=_generation_result("wip: checkpoint before merge\n"),
        ) as finalize_mock, patch(
            "lazy_commit.cli.apply_commit_message",
            return_value=ApplyResult(
                commit_output="[main abc123] wip: checkpoint before merge"
            ),
        ) as apply_mock:
            git_client = git_client_cls.return_value
            git_client.snapshot.return_value = snapshot

            exit_code = run(["--wip", "--apply", "--yes", "--no-copy"])

        self.assertEqual(exit_code, 0)
        load_settings_mock.assert_called_once()
        build_prompt_mock.assert_called_once()
        finalize_mock.assert_called_once_with(
            '{"type":"fix","scope":"","subject":"checkpoint before merge","body":[],"breaking_change":false}',
            wip=True,
        )
        apply_mock.assert_called_once_with(
            git_client,
            "wip: checkpoint before merge\n",
            push=False,
            remote="origin",
            branch=None,
        )

    def test_run_records_generated_commit_in_history(self) -> None:
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
            "lazy_commit.cli.build_generation_payload", return_value=prompt_payload
        ), patch(
            "lazy_commit.cli.request_commit_proposal",
            return_value='{"type":"chore","scope":"cli","subject":"add progress logs","body":[],"breaking_change":false}',
        ), patch(
            "lazy_commit.cli.finalize_generation",
            return_value=_generation_result(),
        ), patch(
            "lazy_commit.cli.record_generated_history"
        ) as record_history_mock, patch("builtins.print"):
            git_client = git_client_cls.return_value
            git_client.snapshot.return_value = snapshot

            exit_code = run(["--no-copy"])

        self.assertEqual(exit_code, 0)
        record_history_mock.assert_called_once_with(
            git_client,
            snapshot,
            "chore(cli): add progress logs\n",
            settings,
        )

    def test_run_list_languages_mode_skips_generation_flow(self) -> None:
        languages = [
            LanguageInfo(code="en", name="English", aliases=("en-gb", "en-us")),
            LanguageInfo(code="zh-cn", name="简体中文", aliases=("cn", "zh")),
        ]
        with patch("lazy_commit.cli.available_languages", return_value=languages), patch(
            "lazy_commit.cli.load_settings"
        ) as load_settings_mock, patch(
            "lazy_commit.cli.GitClient"
        ) as git_client_cls, patch("builtins.print") as mocked_print:
            exit_code = run(["--list-languages"])

        self.assertEqual(exit_code, 0)
        load_settings_mock.assert_not_called()
        git_client_cls.assert_not_called()

        lines = [str(call.args[0]) for call in mocked_print.call_args_list if call.args]
        self._find_line_index(lines, "Supported Languages")
        self._find_line_index(lines, "en (English) aliases: en-gb, en-us")
        self._find_line_index(lines, "zh-cn (简体中文) aliases: cn, zh")

    def test_run_check_i18n_reports_issues_and_exits_non_zero(self) -> None:
        issues = (
            "zh-cn: missing key 'cli.help.lang', falling back to en.",
            "zh-cn: missing key 'ui.none', falling back to en.",
        )
        with patch("lazy_commit.cli.translation_issues", return_value=issues), patch(
            "lazy_commit.cli.load_settings"
        ) as load_settings_mock, patch(
            "lazy_commit.cli.GitClient"
        ) as git_client_cls, patch("builtins.print") as mocked_print:
            exit_code = run(["--check-i18n"])

        self.assertEqual(exit_code, 1)
        load_settings_mock.assert_not_called()
        git_client_cls.assert_not_called()

        lines = [str(call.args[0]) for call in mocked_print.call_args_list if call.args]
        self._find_line_index(lines, "I18n Validation")
        self._find_line_index(lines, "Issue: zh-cn: missing key 'cli.help.lang', falling back to en.")
        self._find_line_index(lines, "Found 2 i18n issue(s).")

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
            "lazy_commit.cli.build_generation_payload", return_value=prompt_payload
        ), patch(
            "lazy_commit.cli.request_commit_proposal",
            return_value='{"type":"chore","scope":"cli","subject":"add progress logs","body":[],"breaking_change":false}',
        ), patch(
            "lazy_commit.cli.finalize_generation",
            return_value=_generation_result(),
        ), patch("builtins.print") as mocked_print:
            git_client = git_client_cls.return_value
            git_client.snapshot.return_value = snapshot

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

    def test_main_prints_llm_error_details_and_hints(self) -> None:
        stderr = io.StringIO()
        error = LLMError(
            "Model API gateway returned HTTP 502 and an HTML error page instead of a JSON API response.",
            details=(
                "Endpoint: https://example.com/models/gemini:generateContent",
                "Response summary: tootaio.com | 502: Bad gateway",
            ),
            hints=("Retry first.",),
        )

        with patch("lazy_commit.cli.run", side_effect=error), patch(
            "sys.stderr",
            stderr,
        ):
            with self.assertRaises(SystemExit) as ctx:
                main()

        self.assertEqual(ctx.exception.code, 2)
        output = stderr.getvalue()
        self.assertIn("lazy-commit error:", output)
        self.assertIn(
            "Detail: Endpoint: https://example.com/models/gemini:generateContent",
            output,
        )
        self.assertIn("Hint: Retry first.", output)


if __name__ == "__main__":
    unittest.main()
