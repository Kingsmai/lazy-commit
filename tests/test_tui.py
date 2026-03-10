from __future__ import annotations

import unittest
from unittest.mock import patch

from lazy_commit.config import Settings
from lazy_commit.errors import ConfigError
from lazy_commit.git_ops import FileChange
from lazy_commit.tui import TUIOptions, _ellipsize, _format_change_label, _wrap_block, run_tui


class TUITests(unittest.TestCase):
    def test_ellipsize_shortens_long_lines(self) -> None:
        self.assertEqual(_ellipsize("abcdef", 5), "ab...")
        self.assertEqual(_ellipsize("abc", 5), "abc")

    def test_wrap_block_preserves_blank_lines(self) -> None:
        wrapped = _wrap_block("alpha beta\n\nsecond block", 6)
        self.assertIn("", wrapped)
        self.assertIn("second", wrapped)

    def test_format_change_label_includes_rename_source(self) -> None:
        renamed = FileChange(
            index_status="R",
            worktree_status=" ",
            path="new_name.py",
            original_path="old_name.py",
        )
        self.assertEqual(
            _format_change_label(renamed), "new_name.py <- old_name.py"
        )

    def test_run_tui_raises_when_curses_is_unavailable(self) -> None:
        settings = Settings(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model_name="gpt-4.1-mini",
            max_context_size=12000,
            provider="openai",
        )

        with patch("lazy_commit.tui.curses", None):
            with self.assertRaises(ConfigError):
                run_tui(settings, TUIOptions())

    def test_run_tui_reports_windows_install_hint_when_curses_is_unavailable(self) -> None:
        settings = Settings(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model_name="gpt-4.1-mini",
            max_context_size=12000,
            provider="openai",
        )

        with patch("lazy_commit.tui.curses", None), patch(
            "lazy_commit.tui.sys.platform", "win32"
        ):
            with self.assertRaises(ConfigError) as context:
                run_tui(settings, TUIOptions())

        self.assertIn("windows-curses", str(context.exception))

    def test_run_tui_reports_windows_python_314_compatibility_hint(self) -> None:
        settings = Settings(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model_name="gpt-4.1-mini",
            max_context_size=12000,
            provider="openai",
        )

        with patch("lazy_commit.tui.curses", None), patch(
            "lazy_commit.tui.sys.platform", "win32"
        ), patch("lazy_commit.tui.sys.version_info", (3, 14, 0)):
            with self.assertRaises(ConfigError) as context:
                run_tui(settings, TUIOptions())

        self.assertIn("Python 3.14+", str(context.exception))


if __name__ == "__main__":
    unittest.main()
