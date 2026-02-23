"""Console rendering helpers."""

from __future__ import annotations

import os
import shutil
import sys
from typing import Any

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"

try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:
    _RICH_AVAILABLE = False
    box = Console = Panel = Table = Text = None  # type: ignore[assignment]
else:
    _RICH_AVAILABLE = True


def use_color() -> bool:
    return sys.stdout.isatty() and os.getenv("NO_COLOR") is None


def colorize(text: str, *codes: str) -> str:
    if not use_color() or not codes:
        return text
    return "".join(codes) + text + RESET


def width(default: int = 80) -> int:
    return max(60, min(120, shutil.get_terminal_size((default, 20)).columns))


def _capture_renderable(renderable: Any) -> str | None:
    if not _RICH_AVAILABLE:
        return None
    color_enabled = use_color()
    console = Console(
        width=width(),
        force_terminal=color_enabled,
        color_system="auto" if color_enabled else None,
        no_color=not color_enabled,
        soft_wrap=True,
        highlight=False,
    )
    with console.capture() as capture:
        console.print(renderable)
    return capture.get().rstrip("\n")


def rule(char: str = "-") -> str:
    return char * width()


def section(title: str) -> str:
    if _RICH_AVAILABLE:
        rendered = _capture_renderable(Text(f"[{title}]", style="bold blue"))
        if rendered is not None:
            return rendered
    return colorize(f"[{title}]", BOLD, BLUE)


def _status(level: str, text: str, ansi_code: str, rich_style: str) -> str:
    prefix = f"[{level}] "
    if _RICH_AVAILABLE:
        rendered = _capture_renderable(Text.assemble((prefix, rich_style), text))
        if rendered is not None:
            return rendered
    return colorize(prefix + text, ansi_code)


def info(text: str) -> str:
    return _status("INFO", text, DIM, "cyan")


def success(text: str) -> str:
    return _status("OK", text, GREEN, "green")


def warn(text: str) -> str:
    return _status("WARN", text, YELLOW, "yellow")


def error(text: str) -> str:
    return _status("ERROR", text, RED, "bold red")


def key_value(label: str, value: str) -> str:
    if _RICH_AVAILABLE:
        rendered = _capture_renderable(Text.assemble((label + ":", "bold cyan"), f" {value}"))
        if rendered is not None:
            return rendered
    return f"{colorize(label + ':', BOLD, CYAN)} {value}"


def render_generation_summary(
    provider: str, model: str, branch: str, file_count: int
) -> str:
    rows = [
        ("Provider", provider),
        ("Model", model),
        ("Branch", branch),
        ("Files", str(file_count)),
    ]
    if _RICH_AVAILABLE:
        table = Table(show_header=False, box=box.SIMPLE, pad_edge=False)
        table.add_column("Field", style="bold cyan", no_wrap=True)
        table.add_column("Value", style="white")
        for label, value in rows:
            table.add_row(Text(label), Text(value))
        rendered = _capture_renderable(table)
        if rendered is not None:
            return rendered
    return "\n".join(key_value(label, value) for label, value in rows)


def render_files(files: list[str]) -> str:
    if not files:
        return "  (none)"
    if _RICH_AVAILABLE:
        table = Table(show_header=True, box=box.SIMPLE_HEAD, pad_edge=False)
        table.add_column("#", justify="right", style="bold cyan", no_wrap=True)
        table.add_column("Path", style="white")
        for index, path in enumerate(files, start=1):
            table.add_row(str(index), Text(path))
        rendered = _capture_renderable(table)
        if rendered is not None:
            return rendered
    return "\n".join(f"  - {path}" for path in files)


def render_message_box(message: str) -> str:
    body = message.rstrip("\n") or ""
    if _RICH_AVAILABLE:
        panel = Panel(
            Text(body),
            title="Commit Message",
            title_align="left",
            border_style="green",
            box=box.ROUNDED,
            padding=(0, 1),
        )
        rendered = _capture_renderable(panel)
        if rendered is not None:
            return rendered
    lines = body.splitlines() or [""]
    content_width = max(len(line) for line in lines)
    border = "+" + "-" * (content_width + 2) + "+"
    body = "\n".join(f"| {line.ljust(content_width)} |" for line in lines)
    return f"{border}\n{body}\n{border}"
