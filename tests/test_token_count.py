from __future__ import annotations

import unittest
from unittest.mock import patch

from lazy_commit.errors import ConfigError
from lazy_commit.token_count import count_tokens, create_token_counter


class _FakeEncoding:
    def __init__(self, name: str, token_count: int) -> None:
        self.name = name
        self._token_count = token_count

    def encode(self, _: str) -> list[int]:
        return [0] * self._token_count

    def decode(self, tokens: list[int]) -> str:
        return "x" * len(tokens)


class _FakeTikToken:
    def encoding_for_model(self, model_name: str) -> _FakeEncoding:
        if model_name == "known-model":
            return _FakeEncoding("known-encoding", 3)
        raise KeyError(model_name)

    def get_encoding(self, encoding_name: str) -> _FakeEncoding:
        if encoding_name == "o200k_base":
            return _FakeEncoding("o200k_base", 4)
        if encoding_name == "cl100k_base":
            return _FakeEncoding("cl100k_base", 5)
        raise KeyError(encoding_name)


class TokenCountTests(unittest.TestCase):
    def test_count_tokens_uses_model_encoding_when_available(self) -> None:
        with patch("lazy_commit.token_count._load_tiktoken", return_value=_FakeTikToken()):
            result = count_tokens("hello world", model_name="known-model")

        self.assertEqual(result.token_count, 3)
        self.assertEqual(result.character_count, len("hello world"))
        self.assertEqual(result.model_name, "known-model")
        self.assertEqual(result.encoding_name, "known-encoding")

    def test_count_tokens_falls_back_to_default_encoding_for_unknown_model(self) -> None:
        with patch("lazy_commit.token_count._load_tiktoken", return_value=_FakeTikToken()):
            result = count_tokens("hello world", model_name="unknown-model")

        self.assertEqual(result.token_count, 4)
        self.assertEqual(result.encoding_name, "o200k_base")

    def test_count_tokens_rejects_unknown_explicit_encoding(self) -> None:
        with patch("lazy_commit.token_count._load_tiktoken", return_value=_FakeTikToken()):
            with self.assertRaises(ConfigError):
                count_tokens(
                    "hello world",
                    model_name="known-model",
                    encoding_name="unknown-encoding",
                )

    def test_create_token_counter_can_truncate_by_token_limit(self) -> None:
        with patch("lazy_commit.token_count._load_tiktoken", return_value=_FakeTikToken()):
            counter = create_token_counter(model_name="known-model")
            truncated = counter.truncate("hello world", max_tokens=2)
        self.assertEqual(counter.encoding_name, "known-encoding")
        self.assertEqual(truncated, "xx")


if __name__ == "__main__":
    unittest.main()
