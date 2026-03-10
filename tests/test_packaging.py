from __future__ import annotations

import unittest
from pathlib import Path


class PackagingTests(unittest.TestCase):
    def test_windows_installs_windows_curses_dependency(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        pyproject_text = (repo_root / "pyproject.toml").read_text(encoding="utf-8")

        self.assertIn(
            '"windows-curses; platform_system == \'Windows\' and python_version < \'3.14\'"',
            pyproject_text,
        )


if __name__ == "__main__":
    unittest.main()
