from __future__ import annotations

import subprocess
import unittest
from dataclasses import dataclass

from lazy_commit.clipboard import (
    _CLIPBOARD_COMMAND_TIMEOUT_SECONDS,
    clipboard_commands,
    copy_text,
)


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

    def test_linux_wayland_prefers_wl_copy(self) -> None:
        commands = clipboard_commands(
            system_name="Linux",
            which=lambda name: "/bin/" + name if name in {"wl-copy", "xclip"} else None,
            env={"WAYLAND_DISPLAY": "wayland-0"},
        )
        self.assertEqual(commands, [["wl-copy"]])

    def test_linux_x11_prefers_xclip_without_wayland(self) -> None:
        commands = clipboard_commands(
            system_name="Linux",
            which=lambda name: (
                "/bin/" + name if name in {"wl-copy", "xclip", "xsel"} else None
            ),
            env={"DISPLAY": ":0"},
        )
        self.assertEqual(commands[0], ["xclip", "-selection", "clipboard"])
        self.assertNotIn(["wl-copy"], commands)

    def test_copy_text_success(self) -> None:
        calls: list[list[str]] = []
        seen_kwargs: dict[str, object] = {}

        def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(cmd)
            seen_kwargs.update(kwargs)
            return _Result(returncode=0)

        result = copy_text(
            "test message",
            run=fake_run,  # type: ignore[arg-type]
            system_name="Linux",
            which=lambda name: "/bin/" + name if name == "xclip" else None,
            env={"DISPLAY": ":0"},
        )
        self.assertTrue(result.ok)
        self.assertIn("xclip -selection clipboard", result.detail)
        self.assertEqual(calls[0], ["xclip", "-selection", "clipboard"])
        self.assertNotIn("capture_output", seen_kwargs)
        self.assertIs(seen_kwargs["stdout"], subprocess.DEVNULL)
        self.assertEqual(
            seen_kwargs["timeout"], _CLIPBOARD_COMMAND_TIMEOUT_SECONDS
        )
        self.assertTrue(hasattr(seen_kwargs["stderr"], "write"))

    def test_copy_text_collects_stderr_from_temp_file(self) -> None:
        def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
            kwargs["stderr"].write("clipboard backend unavailable\n")
            return _Result(returncode=1)

        result = copy_text(
            "test message",
            run=fake_run,  # type: ignore[arg-type]
            system_name="Linux",
            which=lambda name: "/bin/" + name if name == "xclip" else None,
            env={"DISPLAY": ":0"},
        )
        self.assertFalse(result.ok)
        self.assertIn("clipboard backend unavailable", result.detail)

    def test_copy_text_falls_back_after_timeout(self) -> None:
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(cmd)
            if cmd[0] == "wl-copy":
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs["timeout"])
            return _Result(returncode=0)

        result = copy_text(
            "test message",
            run=fake_run,  # type: ignore[arg-type]
            system_name="Linux",
            which=lambda name: "/bin/" + name if name in {"wl-copy", "xclip"} else None,
            env={"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"},
        )
        self.assertTrue(result.ok)
        self.assertEqual(calls[0], ["wl-copy"])
        self.assertEqual(calls[1], ["xclip", "-selection", "clipboard"])

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
