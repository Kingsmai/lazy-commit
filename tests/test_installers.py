from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


@unittest.skipIf(os.name == "nt", "Unix installer; Windows is exercised in CI")
class UnixInstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin with spaces"
        self.bin.mkdir()
        self.log = self.root / "calls.jsonl"
        self.script = Path(__file__).resolve().parents[1] / "scripts/install.sh"
        self.env = dict(os.environ, PATH=str(self.bin), INSTALL_TEST_LOG=str(self.log))
        self._executable("git", "pass")
        self._executable("uv", '''
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['INSTALL_TEST_LOG'], 'a') as stream:
    stream.write(json.dumps(args) + '\\n')
if args[:2] == ['tool', 'install']:
    sys.exit(int(os.environ.get('INSTALL_TEST_FAIL', '0')))
if args == ['tool', 'dir', '--bin']:
    print(Path(__file__).parent)
''')
        self._executable("lazy-commit", "print('lazy-commit test-version')")

    def _executable(self, name: str, body: str) -> None:
        path = self.bin / name
        path.write_text(f"#!{sys.executable}\n{body}\n", encoding="utf-8")
        path.chmod(0o755)

    def _run(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [shutil.which("sh"), str(self.script), str(self.root / "source with spaces")],
            env=self.env, capture_output=True, text=True, check=False,
        )

    def test_installs_quoted_source_and_verifies_command(self) -> None:
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual(calls, [
            ['tool', 'install', '--python', '3.13', '--upgrade',
             '--reinstall-package', 'lazy-commit', str(self.root / 'source with spaces')],
            ['tool', 'update-shell'],
            ['tool', 'dir', '--bin'],
        ])
        self.assertIn("lazy-commit test-version", result.stdout)

    def test_install_failure_stops_before_shell_changes(self) -> None:
        self.env['INSTALL_TEST_FAIL'] = '7'
        result = self._run()
        self.assertEqual(result.returncode, 7)
        self.assertEqual(len(self.log.read_text().splitlines()), 1)
        self.assertNotIn("Installed.", result.stdout)

    def test_missing_git_fails_before_install(self) -> None:
        (self.bin / 'git').unlink()
        result = self._run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Git is required", result.stderr)
        self.assertFalse(self.log.exists())

