from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class I18nSyncScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self._repo_root = Path(__file__).resolve().parents[1]
        self._script_path = self._repo_root / "scripts" / "i18n_sync.py"

    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_generate_pending_template_for_missing_and_invalid_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            locales_dir = temp_root / "locales"
            output_dir = temp_root / "pending"

            self._write_json(
                locales_dir / "en.json",
                {
                    "name": "English",
                    "aliases": ["en"],
                    "yes_answers": ["y", "yes"],
                    "messages": {
                        "msg.alpha": "alpha {name}",
                        "msg.beta": "beta",
                        "msg.gamma": "gamma",
                    },
                },
            )
            self._write_json(
                locales_dir / "zh-cn.json",
                {
                    "name": "简体中文",
                    "aliases": ["zh-CN"],
                    "yes_answers": ["是"],
                    "messages": {
                        "msg.alpha": "阿尔法",
                        "msg.beta": "",
                        "msg.delta": "extra",
                    },
                },
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path),
                    "--locales-dir",
                    str(locales_dir),
                    "--output-dir",
                    str(output_dir),
                    "--locale",
                    "zh-cn",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)

            pending_path = output_dir / "zh-cn.pending.json"
            self.assertTrue(pending_path.exists())
            template_payload = json.loads(pending_path.read_text(encoding="utf-8"))

            self.assertEqual(template_payload["name"], "简体中文")
            self.assertEqual(template_payload["aliases"], ["zh-CN"])
            self.assertEqual(template_payload["yes_answers"], ["是"])
            self.assertEqual(
                template_payload["messages"],
                {
                    "msg.alpha": "alpha {name}",
                    "msg.beta": "beta",
                    "msg.gamma": "gamma",
                },
            )
            self.assertEqual(template_payload["_meta"]["missing_keys"], 1)
            self.assertEqual(template_payload["_meta"]["empty_values"], 1)
            self.assertEqual(template_payload["_meta"]["placeholder_mismatch"], 1)
            self.assertEqual(template_payload["_meta"]["obsolete_keys"], 1)
            self.assertEqual(template_payload["_meta"]["total_pending"], 3)

    def test_up_to_date_locale_removes_stale_template(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            locales_dir = temp_root / "locales"
            output_dir = temp_root / "pending"

            base_payload = {
                "name": "English",
                "aliases": ["en"],
                "yes_answers": ["y", "yes"],
                "messages": {
                    "msg.alpha": "alpha {name}",
                    "msg.beta": "beta",
                },
            }

            self._write_json(locales_dir / "en.json", base_payload)
            self._write_json(
                locales_dir / "zh-cn.json",
                {
                    "name": "简体中文",
                    "aliases": ["zh-CN"],
                    "yes_answers": ["是", "y"],
                    "messages": {
                        "msg.alpha": "阿尔法 {name}",
                        "msg.beta": "贝塔",
                    },
                },
            )

            stale_template = output_dir / "zh-cn.pending.json"
            self._write_json(stale_template, {"messages": {"stale": "value"}})
            self.assertTrue(stale_template.exists())

            result = subprocess.run(
                [
                    sys.executable,
                    str(self._script_path),
                    "--locales-dir",
                    str(locales_dir),
                    "--output-dir",
                    str(output_dir),
                    "--locale",
                    "zh-cn",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
            self.assertIn("up-to-date", result.stdout)
            self.assertFalse(stale_template.exists())


if __name__ == "__main__":
    unittest.main()
