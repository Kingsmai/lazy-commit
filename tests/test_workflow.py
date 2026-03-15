from __future__ import annotations

import threading
import unittest
from unittest.mock import Mock
from unittest.mock import patch

from lazy_commit.config import Settings
from lazy_commit.errors import LLMError
from lazy_commit.prompting import PromptPayload
from lazy_commit.workflow import _run_interruptibly, request_commit_proposal


class WorkflowTests(unittest.TestCase):
    def test_request_commit_proposal_returns_model_text(self) -> None:
        settings = Settings(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model_name="gpt-4.1-mini",
            max_context_size=12000,
            provider="openai",
        )
        payload = PromptPayload(system="system", user="user", context="context")
        client = Mock()
        client.complete.return_value.text = "feat(cli): support ctrl+c\n"

        result = request_commit_proposal(settings, payload, client=client)

        self.assertEqual(result, "feat(cli): support ctrl+c\n")
        client.complete.assert_called_once_with(payload)

    def test_run_interruptibly_reraises_worker_error(self) -> None:
        error = LLMError("request failed")

        with self.assertRaises(LLMError) as context:
            _run_interruptibly(lambda: (_ for _ in ()).throw(error))

        self.assertIs(context.exception, error)

    def test_run_interruptibly_propagates_keyboard_interrupt_while_worker_blocks(self) -> None:
        release_worker = threading.Event()

        def blocked_operation() -> str:
            release_worker.wait(timeout=1)
            return "late result"

        try:
            with patch(
                "lazy_commit.workflow.queue.Queue.get",
                side_effect=KeyboardInterrupt,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    _run_interruptibly(blocked_operation)
        finally:
            release_worker.set()


if __name__ == "__main__":
    unittest.main()
