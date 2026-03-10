from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lazy_commit.history import (
    build_history_entry,
    load_history_entries,
    record_history_entry,
)


class HistoryTests(unittest.TestCase):
    def test_record_and_query_history_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            history_file = Path(tmpdir) / "history.jsonl"
            first = build_history_entry(
                repo_path="/work/demo-one",
                branch="main",
                commit_message="feat(cli): add history browser\n",
                changed_files=["src/lazy_commit/cli.py"],
                generated_at="2026-03-10T10:00:00+08:00",
            )
            second = build_history_entry(
                repo_path="/work/demo-two",
                branch="dev",
                commit_message="fix(ui): tighten output spacing",
                changed_files=["src/lazy_commit/ui.py"],
                generated_at="2026-03-10T11:00:00+08:00",
            )

            record_history_entry(first, path=history_file)
            record_history_entry(second, path=history_file)

            entries = load_history_entries(path=history_file, limit=10)
            self.assertEqual([entry.project_name for entry in entries], ["demo-two", "demo-one"])
            self.assertEqual(entries[1].commit_message, "feat(cli): add history browser")

            filtered = load_history_entries(path=history_file, query="demo-one", limit=10)
            self.assertEqual(len(filtered), 1)
            self.assertEqual(filtered[0].repo_path, "/work/demo-one")

    def test_load_history_ignores_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            history_file = Path(tmpdir) / "missing.jsonl"
            entries = load_history_entries(path=history_file, limit=5)
        self.assertEqual(entries, [])


if __name__ == "__main__":
    unittest.main()
