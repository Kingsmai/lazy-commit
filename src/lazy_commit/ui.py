"""Console rendering helpers."""

from __future__ import annotations

import os
import shutil
import sys
from typing import TYPE_CHECKING, Any

from .history import format_history_timestamp
from .i18n import t

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

if TYPE_CHECKING:
    from .history import HistoryEntry


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
    return _status(t("ui.level.info"), text, DIM, "cyan")


def success(text: str) -> str:
    return _status(t("ui.level.ok"), text, GREEN, "green")


def warn(text: str) -> str:
    return _status(t("ui.level.warn"), text, YELLOW, "yellow")


def error(text: str) -> str:
    return _status(t("ui.level.error"), text, RED, "bold red")


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
        (t("ui.field.provider"), provider),
        (t("ui.field.model"), model),
        (t("ui.field.branch"), branch),
        (t("ui.field.files"), str(file_count)),
    ]
    if _RICH_AVAILABLE:
        table = Table(show_header=False, box=box.SIMPLE, pad_edge=False)
        table.add_column(t("ui.table.field"), style="bold cyan", no_wrap=True)
        table.add_column(t("ui.table.value"), style="white")
        for label, value in rows:
            table.add_row(Text(label), Text(value))
        rendered = _capture_renderable(table)
        if rendered is not None:
            return rendered
    return "\n".join(key_value(label, value) for label, value in rows)


def render_files(files: list[str]) -> str:
    if not files:
        return f"  {t('ui.none')}"
    if _RICH_AVAILABLE:
        table = Table(show_header=True, box=box.SIMPLE_HEAD, pad_edge=False)
        table.add_column("#", justify="right", style="bold cyan", no_wrap=True)
        table.add_column(t("ui.table.path"), style="white")
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
            title=t("ui.commit_message_title"),
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


def render_history(entries: list[HistoryEntry]) -> str:
    if not entries:
        return f"  {t('ui.none')}"
    if _RICH_AVAILABLE:
        table = Table(show_header=True, box=box.SIMPLE_HEAD, pad_edge=False)
        table.add_column("#", justify="right", style="bold cyan", no_wrap=True)
        table.add_column(t("ui.table.generated"), style="white", no_wrap=True)
        table.add_column(t("ui.table.project"), style="bold white", no_wrap=True)
        table.add_column(t("ui.table.branch"), style="white", no_wrap=True)
        table.add_column(t("ui.table.path"), style="white", overflow="fold")
        table.add_column(t("ui.table.message"), style="white", overflow="fold")
        for index, entry in enumerate(entries, start=1):
            table.add_row(
                str(index),
                format_history_timestamp(entry.generated_at),
                entry.project_name,
                entry.branch,
                entry.repo_path,
                entry.subject,
            )
        rendered = _capture_renderable(table)
        if rendered is not None:
            return rendered
    blocks: list[str] = []
    for index, entry in enumerate(entries, start=1):
        blocks.append(
            "\n".join(
                (
                    f"{index}. {entry.subject}",
                    f"   {t('ui.field.generated_at')}: {format_history_timestamp(entry.generated_at)}",
                    f"   {t('ui.field.project')}: {entry.project_name}",
                    f"   {t('ui.field.branch')}: {entry.branch}",
                    f"   {t('ui.field.path')}: {entry.repo_path}",
                )
            )
        )
    return "\n\n".join(blocks)


def render_history_detail(entry: HistoryEntry) -> str:
    rows = [
        (t("ui.field.generated_at"), format_history_timestamp(entry.generated_at)),
        (t("ui.field.project"), entry.project_name),
        (t("ui.field.branch"), entry.branch),
        (t("ui.field.path"), entry.repo_path),
        (t("ui.field.provider"), entry.provider or t("ui.none")),
        (t("ui.field.model"), entry.model_name or t("ui.none")),
    ]
    if _RICH_AVAILABLE:
        table = Table(show_header=False, box=box.SIMPLE, pad_edge=False)
        table.add_column(t("ui.table.field"), style="bold cyan", no_wrap=True)
        table.add_column(t("ui.table.value"), style="white")
        for label, value in rows:
            table.add_row(Text(label), Text(value))
        rendered = _capture_renderable(table)
        if rendered is not None:
            return rendered
    return "\n".join(key_value(label, value) for label, value in rows)
