from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lazy_commit import __version__


class PackagingTests(unittest.TestCase):
    def test_windows_installs_windows_curses_dependency(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        pyproject_text = (repo_root / "pyproject.toml").read_text(encoding="utf-8")

        self.assertIn(
            '"windows-curses>=2.4.2; platform_system == \'Windows\'"',
            pyproject_text,
        )

    def test_package_and_project_versions_match(self) -> None:
        project = Path(__file__).resolve().parents[1] / "pyproject.toml"
        match = re.search(
            r'^version = "([^"]+)"', project.read_text(encoding="utf-8"), re.MULTILINE
        )
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), __version__)

    def test_module_entrypoint_reports_version_outside_repo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-m", "lazy_commit", "--version"],
                cwd=directory, capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"lazy-commit {__version__}")


if __name__ == "__main__":
    unittest.main()
