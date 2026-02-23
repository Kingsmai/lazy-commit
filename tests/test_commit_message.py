from __future__ import annotations

import unittest

from lazy_commit.commit_message import parse_commit_proposal


class ParseCommitProposalTests(unittest.TestCase):
    def test_parse_basic_payload(self) -> None:
        raw = """
        {
          "type": "feat",
          "scope": "cli",
          "subject": "add apply and push flags.",
          "body": ["include --apply flow", "wire push after commit"],
          "breaking_change": false
        }
        """
        proposal = parse_commit_proposal(raw)
        self.assertEqual(proposal.commit_type, "feat")
        self.assertEqual(proposal.scope, "cli")
        self.assertEqual(proposal.subject, "add apply and push flags")
        message = proposal.to_commit_message()
        self.assertIn("feat(cli): add apply and push flags", message)

    def test_invalid_type_falls_back_to_chore(self) -> None:
        raw = """
        {
          "type": "unknown",
          "scope": "cli",
          "subject": "update behavior",
          "body": [],
          "breaking_change": false
        }
        """
        proposal = parse_commit_proposal(raw)
        self.assertEqual(proposal.commit_type, "chore")

    def test_reject_empty_subject(self) -> None:
        raw = """
        {
          "type": "fix",
          "scope": "core",
          "subject": "   ",
          "body": [],
          "breaking_change": false
        }
        """
        with self.assertRaises(Exception):
            parse_commit_proposal(raw)


if __name__ == "__main__":
    unittest.main()

