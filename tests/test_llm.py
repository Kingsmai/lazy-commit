from __future__ import annotations

import unittest

from lazy_commit.llm import _format_http_error, _normalize_openai_base_url


class LLMHelpersTests(unittest.TestCase):
    def test_normalize_openai_base_url_default(self) -> None:
        self.assertEqual(
            _normalize_openai_base_url(None),
            "https://api.openai.com/v1",
        )

    def test_normalize_openai_base_url_adds_v1_for_api_openai_host(self) -> None:
        self.assertEqual(
            _normalize_openai_base_url("https://api.openai.com"),
            "https://api.openai.com/v1",
        )
        self.assertEqual(
            _normalize_openai_base_url("https://api.openai.com/"),
            "https://api.openai.com/v1",
        )

    def test_normalize_openai_base_url_keeps_custom_paths(self) -> None:
        self.assertEqual(
            _normalize_openai_base_url("https://api.openai.com/v1"),
            "https://api.openai.com/v1",
        )
        self.assertEqual(
            _normalize_openai_base_url("https://example.com/openai/v1"),
            "https://example.com/openai/v1",
        )

    def test_format_http_403_1010_has_actionable_hint(self) -> None:
        msg = _format_http_error(
            403,
            "<html>Access denied. error code: 1010</html>",
            "https://api.openai.com/chat/completions",
        )
        self.assertIn("HTTP 403 (error code 1010)", msg)
        self.assertIn("LAZY_COMMIT_BASE_URL=https://api.openai.com/v1", msg)

    def test_format_http_error_sanitizes_query_and_extracts_message(self) -> None:
        msg = _format_http_error(
            401,
            '{"error":{"message":"Invalid API key","type":"invalid_request_error","code":"invalid_api_key"}}',
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=secret",
        )
        self.assertIn("HTTP 401", msg)
        self.assertNotIn("key=secret", msg)
        self.assertIn("Invalid API key", msg)


if __name__ == "__main__":
    unittest.main()

