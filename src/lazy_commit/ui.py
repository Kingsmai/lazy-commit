"""Console rendering helpers."""

from __future__ import annotations

import os
import shutil
import sys

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"


def use_color() -> bool:
    return sys.stdout.isatty() and os.getenv("NO_COLOR") is None


def colorize(text: str, *codes: str) -> str:
    if not use_color() or not codes:
        return text
    return "".join(codes) + text + RESET


def width(default: int = 80) -> int:
    return max(60, min(120, shutil.get_terminal_size((default, 20)).columns))


def rule(char: str = "-") -> str:
    return char * width()


def section(title: str) -> str:
    return colorize(f"[{title}]", BOLD, BLUE)


def info(text: str) -> str:
    return colorize(text, DIM)


def success(text: str) -> str:
    return colorize(text, GREEN)


def warn(text: str) -> str:
    return colorize(text, YELLOW)


def error(text: str) -> str:
    return colorize(text, RED)


def key_value(label: str, value: str) -> str:
    return f"{colorize(label + ':', BOLD, CYAN)} {value}"


def render_files(files: list[str]) -> str:
    if not files:
        return "  (none)"
    return "\n".join(f"  - {path}" for path in files)


def render_message_box(message: str) -> str:
    lines = (message.rstrip("\n") or "").splitlines() or [""]
    content_width = max(len(line) for line in lines)
    border = "+" + "-" * (content_width + 2) + "+"
    body = "\n".join(f"| {line.ljust(content_width)} |" for line in lines)
    return f"{border}\n{body}\n{border}"

