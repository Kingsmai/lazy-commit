"""Clipboard helpers with cross-platform command fallback."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Callable, Mapping

from .i18n import t

_CLIPBOARD_COMMAND_TIMEOUT_SECONDS = 3.0


@dataclass(frozen=True)
class CopyResult:
    """Result of a clipboard copy attempt."""

    ok: bool
    detail: str


def _is_wsl(env: Mapping[str, str]) -> bool:
    return "WSL_DISTRO_NAME" in env or "WSL_INTEROP" in env


def _linux_clipboard_candidates(env: Mapping[str, str]) -> list[list[str]]:
    has_wayland = bool(env.get("WAYLAND_DISPLAY"))
    has_x11 = bool(env.get("DISPLAY"))

    candidates: list[list[str]] = []
    if _is_wsl(env):
        candidates.append(["clip.exe"])

    if has_wayland:
        candidates.append(["wl-copy"])

    if has_x11:
        candidates.extend(
            [
                ["xclip", "-selection", "clipboard"],
                ["xsel", "--clipboard", "--input"],
            ]
        )

    if not has_wayland and not has_x11:
        candidates.extend(
            [
                ["wl-copy"],
                ["xclip", "-selection", "clipboard"],
                ["xsel", "--clipboard", "--input"],
            ]
        )

    return candidates


def clipboard_commands(
    *,
    system_name: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    env: Mapping[str, str] | None = None,
) -> list[list[str]]:
    """Return candidate clipboard commands ordered by preference."""
    resolved_system = (system_name or platform.system()).lower()
    resolved_env = dict(os.environ if env is None else env)

    candidates: list[list[str]] = []
    if resolved_system == "windows":
        candidates.append(["clip"])
    elif resolved_system == "darwin":
        candidates.append(["pbcopy"])
    else:
        # Linux and similar Unix systems.
        candidates.extend(_linux_clipboard_candidates(resolved_env))

    available: list[list[str]] = []
    for cmd in candidates:
        if which(cmd[0]):
            available.append(cmd)
    return available


def _run_clipboard_command(
    cmd: list[str],
    text: str,
    *,
    run: Callable[..., subprocess.CompletedProcess[str]],
) -> tuple[subprocess.CompletedProcess[str], str]:
    # Avoid PIPE capture here. Some Linux clipboard tools daemonize and inherit
    # stdout/stderr, which keeps subprocess.run() waiting for pipe EOF forever.
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr_buffer:
        completed = run(
            cmd,
            input=text,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=stderr_buffer,
            check=False,
            timeout=_CLIPBOARD_COMMAND_TIMEOUT_SECONDS,
        )
        stderr_buffer.seek(0)
        return completed, stderr_buffer.read().strip()


def copy_text(
    text: str,
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    system_name: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    env: Mapping[str, str] | None = None,
) -> CopyResult:
    """Copy text to clipboard using the first available command."""
    commands = clipboard_commands(system_name=system_name, which=which, env=env)
    if not commands:
        return CopyResult(
            ok=False,
            detail=t(
                "clipboard.error.command_not_found",
                commands="pbcopy/clip/wl-copy/xclip/xsel",
            ),
        )

    failures: list[str] = []
    for cmd in commands:
        try:
            completed, stderr = _run_clipboard_command(cmd, text, run=run)
        except subprocess.TimeoutExpired:
            failures.append(
                f"{' '.join(cmd)} (timed out after {_CLIPBOARD_COMMAND_TIMEOUT_SECONDS:g}s)"
            )
            continue
        except OSError as exc:
            failures.append(f"{' '.join(cmd)} ({exc})")
            continue

        if completed.returncode == 0:
            return CopyResult(
                ok=True,
                detail=t("clipboard.success.copied_via", command=" ".join(cmd)),
            )

        failures.append(f"{' '.join(cmd)} ({stderr or f'exit={completed.returncode}'})")

    return CopyResult(
        ok=False,
        detail=(
            t("clipboard.error.copy_failed_all", failures=", ".join(failures))
            if failures
            else t("clipboard.error.copy_failed")
        ),
    )
