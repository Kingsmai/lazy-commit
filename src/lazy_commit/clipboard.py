"""Clipboard helpers with cross-platform command fallback."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable, Mapping


@dataclass(frozen=True)
class CopyResult:
    """Result of a clipboard copy attempt."""

    ok: bool
    detail: str


def _is_wsl(env: Mapping[str, str]) -> bool:
    return "WSL_DISTRO_NAME" in env or "WSL_INTEROP" in env


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
        if _is_wsl(resolved_env):
            candidates.append(["clip.exe"])
        candidates.extend(
            [
                ["wl-copy"],
                ["xclip", "-selection", "clipboard"],
                ["xsel", "--clipboard", "--input"],
            ]
        )

    available: list[list[str]] = []
    for cmd in candidates:
        if which(cmd[0]):
            available.append(cmd)
    return available


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
            detail=(
                "Clipboard command not found. Install one of: "
                "pbcopy/clip/wl-copy/xclip/xsel."
            ),
        )

    failures: list[str] = []
    for cmd in commands:
        completed = run(
            cmd,
            input=text,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode == 0:
            return CopyResult(ok=True, detail=f"Copied to clipboard via {' '.join(cmd)}.")

        stderr = (completed.stderr or "").strip()
        failures.append(f"{' '.join(cmd)} ({stderr or f'exit={completed.returncode}'})")

    return CopyResult(
        ok=False,
        detail=(
            "Clipboard copy failed for all commands: " + ", ".join(failures)
            if failures
            else "Clipboard copy failed."
        ),
    )

