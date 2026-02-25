from __future__ import annotations

import unittest
from unittest.mock import patch

from lazy_commit.i18n import (
    DEFAULT_LANGUAGE,
    ZH_CN_LANGUAGE,
    detect_language,
    get_language,
    is_affirmative,
    normalize_language,
    peek_cli_language,
    set_language,
    t,
)


class I18nTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_language = get_language()
        set_language("en")

    def tearDown(self) -> None:
        set_language(self._original_language)

    def test_normalize_language_aliases(self) -> None:
        self.assertEqual(normalize_language("en-US"), DEFAULT_LANGUAGE)
        self.assertEqual(normalize_language("zh"), ZH_CN_LANGUAGE)
        self.assertEqual(normalize_language("zh_CN"), ZH_CN_LANGUAGE)
        self.assertEqual(normalize_language("unknown"), DEFAULT_LANGUAGE)

    def test_detect_language_prefers_explicit_value(self) -> None:
        with patch.dict("os.environ", {"LAZY_COMMIT_LANG": "zh-CN"}, clear=False):
            self.assertEqual(detect_language("en"), DEFAULT_LANGUAGE)

    def test_detect_language_uses_env_when_no_explicit_value(self) -> None:
        with patch.dict("os.environ", {"LAZY_COMMIT_LANG": "zh-CN"}, clear=False):
            self.assertEqual(detect_language(None), ZH_CN_LANGUAGE)

    def test_peek_cli_language_supports_both_argument_styles(self) -> None:
        self.assertEqual(peek_cli_language(["--lang", "zh-CN"]), "zh-CN")
        self.assertEqual(peek_cli_language(["--lang=zh-CN"]), "zh-CN")
        self.assertIsNone(peek_cli_language(["--apply"]))

    def test_translation_switches_with_language(self) -> None:
        set_language("zh-CN")
        self.assertEqual(t("cli.log.loading_settings"), "正在加载配置...")
        self.assertTrue(is_affirmative("是"))
        self.assertTrue(is_affirmative("yes"))


if __name__ == "__main__":
    unittest.main()
