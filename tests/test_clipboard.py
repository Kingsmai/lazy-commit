from __future__ import annotations

import unittest
from dataclasses import dataclass

from lazy_commit.clipboard import clipboard_commands, copy_text


@dataclass
class _Result:
    returncode: int
    stderr: str = ""


class ClipboardTests(unittest.TestCase):
    def test_windows_prefers_clip(self) -> None:
        commands = clipboard_commands(
            system_name="Windows",
            which=lambda name: "/bin/" + name if name == "clip" else None,
            env={},
        )
        self.assertEqual(commands, [["clip"]])

    def test_wsl_prefers_clip_exe(self) -> None:
        commands = clipboard_commands(
            system_name="Linux",
            which=lambda name: "/bin/" + name if name in {"clip.exe", "xclip"} else None,
            env={"WSL_DISTRO_NAME": "Ubuntu"},
        )
        self.assertEqual(commands[0], ["clip.exe"])
        self.assertIn(["xclip", "-selection", "clipboard"], commands)

    def test_copy_text_success(self) -> None:
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(cmd)
            return _Result(returncode=0)

        result = copy_text(
            "test message",
            run=fake_run,  # type: ignore[arg-type]
            system_name="Linux",
            which=lambda name: "/bin/" + name if name == "xclip" else None,
            env={},
        )
        self.assertTrue(result.ok)
        self.assertIn("xclip -selection clipboard", result.detail)
        self.assertEqual(calls[0], ["xclip", "-selection", "clipboard"])

    def test_copy_text_when_no_command_available(self) -> None:
        result = copy_text(
            "test message",
            system_name="Linux",
            which=lambda _: None,
            env={},
        )
        self.assertFalse(result.ok)
        self.assertIn("Clipboard command not found", result.detail)


if __name__ == "__main__":
    unittest.main()

