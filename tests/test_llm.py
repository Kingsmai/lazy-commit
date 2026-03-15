from __future__ import annotations

import io
import urllib.error
import unittest
from unittest.mock import patch

from lazy_commit.errors import LLMError
from lazy_commit.llm import (
    _build_http_error,
    _normalize_openai_base_url,
    _post_json,
)


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
        error = _build_http_error(
            403,
            "<html>Access denied. error code: 1010</html>",
            "https://api.openai.com/chat/completions",
        )
        self.assertIn("HTTP 403", str(error))
        self.assertTrue(
            any(
                "gateway or WAF" in hint or "api.openai.com/v1" in hint
                for hint in error.hints
            )
        )

    def test_format_http_error_sanitizes_query_and_extracts_message(self) -> None:
        error = _build_http_error(
            401,
            '{"error":{"message":"Invalid API key","type":"invalid_request_error","code":"invalid_api_key"}}',
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=secret",
        )
        self.assertIn("HTTP 401", str(error))
        self.assertTrue(
            any(
                (
                    "Endpoint: "
                    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
                )
                == detail
                for detail in error.details
            )
        )
        self.assertFalse(any("key=secret" in detail for detail in error.details))
        self.assertTrue(any("Invalid API key" in detail for detail in error.details))

    def test_post_json_http_gateway_html_error_is_user_friendly(self) -> None:
        body = (
            "<!DOCTYPE html><html><head>"
            "<title>tootaio.com | 502: Bad gateway</title>"
            "</head><body>Bad gateway</body></html>"
        ).encode("utf-8")
        http_error = urllib.error.HTTPError(
            "https://example.com/models/gemini:generateContent?key=secret",
            502,
            "Bad gateway",
            {
                "Content-Type": "text/html; charset=UTF-8",
                "CF-Ray": "abc123",
            },
            io.BytesIO(body),
        )

        with patch(
            "lazy_commit.llm.urllib.request.urlopen",
            side_effect=http_error,
        ):
            with self.assertRaises(LLMError) as ctx:
                _post_json(
                    "https://example.com/models/gemini:generateContent?key=secret",
                    body={"hello": "world"},
                    headers={"Content-Type": "application/json"},
                )

        error = ctx.exception
        self.assertIn("HTTP 502", str(error))
        self.assertIn("HTML error page", str(error))
        self.assertTrue(
            any(
                detail
                == "Endpoint: https://example.com/models/gemini:generateContent"
                for detail in error.details
            )
        )
        self.assertTrue(
            any(
                "Response summary: tootaio.com | 502: Bad gateway" in detail
                for detail in error.details
            )
        )
        self.assertTrue(
            any("exact cause is unavailable" in detail for detail in error.details)
        )
        self.assertTrue(any("Retry first." in hint for hint in error.hints))
        self.assertTrue(
            any("LAZY_COMMIT_BASE_URL" in hint for hint in error.hints)
        )
        self.assertTrue(
            any(
                "https://generativelanguage.googleapis.com/v1beta" in hint
                for hint in error.hints
            )
        )

    def test_post_json_timeout_is_reported_as_llm_error(self) -> None:
        with patch(
            "lazy_commit.llm.urllib.request.urlopen",
            side_effect=TimeoutError("read operation timed out"),
        ):
            with self.assertRaises(LLMError) as ctx:
                _post_json(
                    "https://example.com/models/gemini:generateContent?key=secret",
                    body={"hello": "world"},
                    headers={"Content-Type": "application/json"},
                    timeout=5,
                    attempts=2,
                )

        message = str(ctx.exception)
        self.assertIn("timed out after 5s", message)
        self.assertIn("2 attempt(s)", message)
        self.assertTrue(
            any(
                detail
                == "Endpoint: https://example.com/models/gemini:generateContent"
                for detail in ctx.exception.details
            )
        )
        self.assertFalse(any("key=secret" in detail for detail in ctx.exception.details))

    def test_post_json_retries_after_timeout_and_succeeds(self) -> None:
        class _Response:
            def __enter__(self) -> _Response:
                return self

            def __exit__(self, *_args: object) -> bool:
                return False

            def read(self) -> bytes:
                return b'{"ok":true}'

        with patch(
            "lazy_commit.llm.urllib.request.urlopen",
            side_effect=[TimeoutError("timeout"), _Response()],
        ) as mocked_urlopen:
            data = _post_json(
                "https://example.com/v1/chat/completions",
                body={"hello": "world"},
                headers={"Authorization": "Bearer test"},
                timeout=5,
                attempts=2,
            )

        self.assertEqual(data, {"ok": True})
        self.assertEqual(mocked_urlopen.call_count, 2)


if __name__ == "__main__":
    unittest.main()
