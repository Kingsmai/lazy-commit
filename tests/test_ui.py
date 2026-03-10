from __future__ import annotations

import unittest
from unittest.mock import patch

from lazy_commit import ui
from lazy_commit.history import HistoryEntry
from lazy_commit.i18n import get_language, set_language


class UIFallbackRenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_language = get_language()
        set_language("en")

    def tearDown(self) -> None:
        set_language(self._original_language)

    def test_render_generation_summary_contains_main_fields(self) -> None:
        with patch("lazy_commit.ui._RICH_AVAILABLE", False), patch(
            "lazy_commit.ui.use_color", return_value=False
        ):
            rendered = ui.render_generation_summary(
                provider="openai",
                model="gpt-4.1-mini",
                branch="main",
                file_count=3,
            )

        self.assertIn("Provider: openai", rendered)
        self.assertIn("Model: gpt-4.1-mini", rendered)
        self.assertIn("Branch: main", rendered)
        self.assertIn("Files: 3", rendered)

    def test_render_files_fallback_uses_bulleted_list(self) -> None:
        with patch("lazy_commit.ui._RICH_AVAILABLE", False):
            rendered = ui.render_files(["src/lazy_commit/cli.py", "tests/test_cli.py"])
        self.assertIn("  - src/lazy_commit/cli.py", rendered)
        self.assertIn("  - tests/test_cli.py", rendered)

    def test_render_message_box_fallback_has_ascii_borders(self) -> None:
        with patch("lazy_commit.ui._RICH_AVAILABLE", False):
            rendered = ui.render_message_box("feat(cli): improve output\n\nadd details")
        self.assertIn("+", rendered)
        self.assertIn("| feat(cli): improve output |", rendered)
        self.assertIn("| add details               |", rendered)

    def test_render_history_fallback_contains_project_and_path(self) -> None:
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
        with patch("lazy_commit.ui._RICH_AVAILABLE", False):
            rendered = ui.render_history(entries)

        self.assertIn("1. feat(cli): add history browser", rendered)
        self.assertIn("Project: lazy-commit", rendered)
        self.assertIn("Path: /tmp/lazy-commit", rendered)

    def test_render_history_detail_fallback_contains_metadata(self) -> None:
        entry = HistoryEntry(
            generated_at="2026-03-10T12:34:56+08:00",
            project_name="lazy-commit",
            repo_path="/tmp/lazy-commit",
            branch="main",
            commit_message="feat(cli): add history browser",
            changed_files=("src/lazy_commit/cli.py",),
            provider="openai",
            model_name="gpt-4.1-mini",
        )
        with patch("lazy_commit.ui._RICH_AVAILABLE", False), patch(
            "lazy_commit.ui.use_color", return_value=False
        ):
            rendered = ui.render_history_detail(entry)

        self.assertIn("Generated: 2026-03-10 12:34:56+08:00", rendered)
        self.assertIn("Project: lazy-commit", rendered)
        self.assertIn("Provider: openai", rendered)
        self.assertIn("Model: gpt-4.1-mini", rendered)

    def test_status_helpers_keep_original_message(self) -> None:
        with patch("lazy_commit.ui._RICH_AVAILABLE", False), patch(
            "lazy_commit.ui.use_color", return_value=False
        ):
            self.assertIn("Loading settings...", ui.info("Loading settings..."))
            self.assertIn("Done.", ui.success("Done."))
            self.assertIn("No changes.", ui.warn("No changes."))
            self.assertIn("fatal", ui.error("fatal"))


if __name__ == "__main__":
    unittest.main()
