from __future__ import annotations

import os
import unittest

from lazy_commit.config import GEMINI_PROVIDER, OPENAI_PROVIDER, detect_provider, load_settings


class ConfigTests(unittest.TestCase):
    def test_detect_provider_from_model(self) -> None:
        self.assertEqual(detect_provider("gemini-2.0-flash", None), GEMINI_PROVIDER)
        self.assertEqual(detect_provider("gpt-4.1-mini", None), OPENAI_PROVIDER)

    def test_detect_provider_from_url(self) -> None:
        url = "https://generativelanguage.googleapis.com/v1beta"
        self.assertEqual(detect_provider("custom-model", url), GEMINI_PROVIDER)

    def test_load_settings_from_env(self) -> None:
        old = dict(os.environ)
        try:
            os.environ["LAZY_COMMIT_API_KEY"] = "test-key"
            os.environ["LAZY_COMMIT_BASE_URL"] = "https://api.openai.com/v1"
            os.environ["LAZY_COMMIT_OPENAI_MODEL_NAME"] = "gpt-4.1-mini"
            os.environ["LAZY_COMMIT_MAX_CONTEXT_SIZE"] = "1000"
            settings = load_settings()
            self.assertEqual(settings.api_key, "test-key")
            self.assertEqual(settings.model_name, "gpt-4.1-mini")
            self.assertEqual(settings.max_context_size, 1000)
        finally:
            os.environ.clear()
            os.environ.update(old)


if __name__ == "__main__":
    unittest.main()

