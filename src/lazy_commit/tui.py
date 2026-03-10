"""Curses-based full-screen TUI for lazy-commit."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import textwrap
from typing import Any

try:
    import curses
except ImportError:  # pragma: no cover - platform-specific fallback.
    curses = None  # type: ignore[assignment]

from .clipboard import copy_text
from .config import Settings
from .errors import ConfigError, GitError, LLMError, LazyCommitError
from .git_ops import FileChange, GitClient, RepoSnapshot
from .i18n import t
from .workflow import (
    apply_commit_message,
    build_generation_payload,
    finalize_generation,
    record_generated_history,
    request_commit_proposal,
)

_MIN_ROWS = 20
_MIN_COLS = 80
_FOCUS_ORDER = ("files", "diff", "message")


@dataclass(frozen=True)
class TUIOptions:
    """Runtime options honored by the interactive TUI."""

    remote: str = "origin"
    branch: str | None = None
    copy: bool = True
    wip: bool = False
    token_model: str | None = None
    token_encoding: str | None = None


def _tui_unavailable_message() -> str:
    if sys.platform == "win32":
        if sys.version_info >= (3, 14):
            return t("cli.error.tui_unavailable_windows_py314")
        return t("cli.error.tui_unavailable_windows")
    return t("cli.error.tui_unavailable")


def _ellipsize(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def _wrap_block(text: str, width: int) -> list[str]:
    if width <= 1:
        return [text[:width]]

    wrapped: list[str] = []
    for raw_line in text.splitlines():
        expanded = raw_line.expandtabs(4)
        if not expanded:
            wrapped.append("")
            continue
        pieces = textwrap.wrap(
            expanded,
            width=width,
            replace_whitespace=False,
            drop_whitespace=False,
            break_long_words=False,
            break_on_hyphens=False,
        )
        wrapped.extend(pieces or [""])
    return wrapped or [""]


def _first_non_empty_line(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return fallback


def _format_change_label(change: FileChange) -> str:
    if change.original_path:
        return f"{change.path} <- {change.original_path}"
    return change.path


def _safe_addnstr(
    window: Any,
    y: int,
    x: int,
    text: str,
    width: int,
    attr: int = 0,
) -> None:
    if width <= 0 or y < 0 or x < 0:
        return
    try:
        window.addnstr(y, x, text, width, attr)
    except Exception:  # pragma: no cover - curses raises platform-specific errors.
        return


class LazyCommitTUI:
    """Stateful curses application for browsing changes and applying commits."""

    def __init__(
        self,
        settings: Settings,
        options: TUIOptions,
        *,
        git: GitClient | None = None,
    ) -> None:
        self.settings = settings
        self.options = options
        self.git = git or GitClient()
        self.repo_root = ""
        self.repo_name = ""

        self.snapshot = RepoSnapshot(
            branch="",
            status_short="",
            staged_diff="",
            unstaged_diff="",
            untracked_files="",
            changed_files=[],
            recent_commits="",
        )
        self.file_changes: list[FileChange] = []
        self.selected_index = 0
        self.file_scroll = 0
        self.diff_scroll = 0
        self.message_scroll = 0
        self.focus = "files"
        self.show_help = False
        self.generated_message = ""
        self.diff_text = t("tui.empty.no_file_selected")
        self.status_message = t("tui.status.ready")
        self.status_level = "info"

        self._screen: Any | None = None
        self._colors_enabled = False

    def run(self) -> int:
        if curses is None:
            raise ConfigError(_tui_unavailable_message())

        self.git.ensure_repo()
        self.repo_root = self.git.repo_root()
        self.repo_name = Path(self.repo_root).name or self.repo_root
        self.refresh_snapshot(preserve_selection=False)
        return curses.wrapper(self._main)

    def _main(self, screen: Any) -> int:
        self._screen = screen
        screen.keypad(True)
        try:
            curses.curs_set(0)
        except Exception:  # pragma: no cover - terminal-specific.
            pass
        self._init_colors()

        while True:
            self._render()
            key = screen.getch()
            result = self._handle_key(key)
            if result is not None:
                return result

    def _init_colors(self) -> None:
        if curses is None or not curses.has_colors():
            return
        curses.start_color()
        if hasattr(curses, "use_default_colors"):
            curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_GREEN, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.init_pair(4, curses.COLOR_RED, -1)
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_CYAN)
        self._colors_enabled = True

    def _color(self, level: str) -> int:
        if not self._colors_enabled or curses is None:
            return 0
        mapping = {
            "info": curses.color_pair(1),
            "ok": curses.color_pair(2),
            "warn": curses.color_pair(3),
            "error": curses.color_pair(4),
            "focus": curses.color_pair(5),
        }
        return mapping.get(level, 0)

    @property
    def selected_change(self) -> FileChange | None:
        if not self.file_changes:
            return None
        if self.selected_index < 0 or self.selected_index >= len(self.file_changes):
            return None
        return self.file_changes[self.selected_index]

    def _set_status(self, message: str, level: str = "info") -> None:
        self.status_message = message
        self.status_level = level

    def _render(self) -> None:
        if self._screen is None:
            return

        screen = self._screen
        screen.erase()
        rows, cols = screen.getmaxyx()
        if rows < _MIN_ROWS or cols < _MIN_COLS:
            message = t(
                "tui.error.terminal_too_small",
                min_cols=_MIN_COLS,
                min_rows=_MIN_ROWS,
            )
            _safe_addnstr(
                screen,
                0,
                0,
                message,
                cols - 1,
                self._color("warn") | getattr(curses, "A_BOLD", 0),
            )
            _safe_addnstr(screen, rows - 1, 0, t("tui.footer"), cols - 1)
            screen.refresh()
            return

        self._draw_header(screen, cols)
        self._draw_body(screen, rows, cols)
        self._draw_footer(screen, rows, cols)
        if self.show_help:
            self._draw_help_overlay(screen, rows, cols)
        screen.refresh()

    def _draw_header(self, screen: Any, cols: int) -> None:
        title = (
            f"{t('tui.title')} | {t('ui.field.project')}: {self.repo_name} | "
            f"{t('ui.field.branch')}: {self.snapshot.branch or t('ui.none')} | "
            f"{t('ui.field.model')}: {self.settings.model_name}"
        )
        selected = self.selected_change.path if self.selected_change else t("ui.none")
        summary = (
            f"{t('tui.label.focus')}: {t(f'tui.focus.{self.focus}')} | "
            f"{t('ui.field.files')}: {len(self.file_changes)} | "
            f"{t('tui.label.selected')}: {selected}"
        )
        _safe_addnstr(
            screen,
            0,
            0,
            title,
            cols - 1,
            self._color("info") | getattr(curses, "A_BOLD", 0),
        )
        _safe_addnstr(screen, 1, 0, summary, cols - 1, getattr(curses, "A_DIM", 0))

    def _draw_body(self, screen: Any, rows: int, cols: int) -> None:
        top = 2
        bottom = 2
        body_height = rows - top - bottom
        left_width = max(28, min(42, cols // 3))
        right_width = cols - left_width - 1
        diff_height = max(8, body_height // 2)
        message_height = body_height - diff_height - 1

        files_win = screen.derwin(body_height, left_width, top, 0)
        diff_win = screen.derwin(diff_height, right_width, top, left_width + 1)
        message_win = screen.derwin(
            message_height,
            right_width,
            top + diff_height + 1,
            left_width + 1,
        )

        self._draw_files_pane(files_win)
        self._draw_text_pane(
            diff_win,
            title=t("tui.pane.diff"),
            text=self.diff_text or t("tui.empty.no_diff"),
            focus="diff",
            scroll_attr="diff_scroll",
        )
        message_text = self.generated_message.rstrip("\n") or t("tui.empty.no_message")
        self._draw_text_pane(
            message_win,
            title=t("ui.commit_message_title"),
            text=message_text,
            focus="message",
            scroll_attr="message_scroll",
        )

    def _draw_files_pane(self, window: Any) -> None:
        height, width = window.getmaxyx()
        self._draw_box(window, t("tui.pane.files"), focused=self.focus == "files")
        visible_rows = max(1, height - 2)
        if not self.file_changes:
            _safe_addnstr(window, 1, 1, t("tui.empty.no_files"), width - 2)
            return

        self._ensure_file_selection_visible(visible_rows)
        start = self.file_scroll
        end = min(len(self.file_changes), start + visible_rows)
        for row, change_index in enumerate(range(start, end), start=1):
            change = self.file_changes[change_index]
            label = f"{change.status_code:>2} {_format_change_label(change)}"
            attr = 0
            if change_index == self.selected_index:
                attr = getattr(curses, "A_REVERSE", 0)
                if self.focus == "files":
                    attr |= self._color("focus")
            _safe_addnstr(window, row, 1, _ellipsize(label, width - 2), width - 2, attr)

    def _ensure_file_selection_visible(self, visible_rows: int) -> None:
        if self.selected_index < self.file_scroll:
            self.file_scroll = self.selected_index
        elif self.selected_index >= self.file_scroll + visible_rows:
            self.file_scroll = self.selected_index - visible_rows + 1
        max_scroll = max(0, len(self.file_changes) - visible_rows)
        self.file_scroll = max(0, min(self.file_scroll, max_scroll))

    def _draw_text_pane(
        self,
        window: Any,
        *,
        title: str,
        text: str,
        focus: str,
        scroll_attr: str,
    ) -> None:
        height, width = window.getmaxyx()
        self._draw_box(window, title, focused=self.focus == focus)
        wrapped = _wrap_block(text, max(1, width - 2))
        visible_rows = max(1, height - 2)
        scroll = getattr(self, scroll_attr)
        max_scroll = max(0, len(wrapped) - visible_rows)
        scroll = max(0, min(scroll, max_scroll))
        setattr(self, scroll_attr, scroll)

        for row in range(visible_rows):
            index = scroll + row
            if index >= len(wrapped):
                break
            _safe_addnstr(window, row + 1, 1, wrapped[index], width - 2)

    def _draw_box(self, window: Any, title: str, *, focused: bool) -> None:
        window.box()
        prefix = "* " if focused else ""
        attr = getattr(curses, "A_BOLD", 0)
        if focused:
            attr |= self._color("info")
        _safe_addnstr(window, 0, 2, f"{prefix}{title}", max(1, window.getmaxyx()[1] - 4), attr)

    def _draw_footer(self, screen: Any, rows: int, cols: int) -> None:
        _safe_addnstr(
            screen,
            rows - 2,
            0,
            self.status_message,
            cols - 1,
            self._color(self.status_level) | getattr(curses, "A_BOLD", 0),
        )
        _safe_addnstr(
            screen,
            rows - 1,
            0,
            t("tui.footer"),
            cols - 1,
            getattr(curses, "A_DIM", 0),
        )

    def _draw_help_overlay(self, screen: Any, rows: int, cols: int) -> None:
        help_lines = t("tui.help.body").splitlines()
        box_height = min(rows - 4, len(help_lines) + 4)
        box_width = min(cols - 6, max(len(line) for line in help_lines) + 6)
        start_y = max(2, (rows - box_height) // 2)
        start_x = max(3, (cols - box_width) // 2)
        window = screen.derwin(box_height, box_width, start_y, start_x)
        self._draw_box(window, t("tui.help.title"), focused=False)
        for row, line in enumerate(help_lines[: box_height - 2], start=1):
            _safe_addnstr(window, row, 1, line, box_width - 2)

    def _handle_key(self, key: int) -> int | None:
        if key in {ord("q"), 27}:
            return 0

        if key in {ord("?"), getattr(curses, "KEY_F1", -1)}:
            self.show_help = not self.show_help
            return None

        if self.show_help:
            self.show_help = False
            return None

        if key in {9, getattr(curses, "KEY_BTAB", -1)}:
            direction = -1 if key == getattr(curses, "KEY_BTAB", -1) else 1
            self._cycle_focus(direction)
            return None

        if key == getattr(curses, "KEY_RESIZE", -1):
            return None

        if key in {ord("r"), ord("R")}:
            self.refresh_snapshot()
            self._set_status(t("tui.status.refreshed"), "ok")
            return None

        if key in {ord("g"), ord("G")}:
            self._generate_message()
            return None

        if key in {ord("y"), ord("Y")}:
            self._copy_message()
            return None

        if key in {ord("a"), ord("A")}:
            self._stage_all()
            return None

        if key in {ord("s"), ord("S")}:
            self._toggle_stage_selected()
            return None

        if key in {ord("c"), ord("C")}:
            self._commit(push=False)
            return None

        if key in {ord("p"), ord("P")}:
            self._commit(push=True)
            return None

        if key in {ord("j"), getattr(curses, "KEY_DOWN", -1)}:
            self._move_current_pane(1)
            return None

        if key in {ord("k"), getattr(curses, "KEY_UP", -1)}:
            self._move_current_pane(-1)
            return None

        if key == getattr(curses, "KEY_NPAGE", -1):
            self._page_current_pane(1)
            return None

        if key == getattr(curses, "KEY_PPAGE", -1):
            self._page_current_pane(-1)
            return None

        return None

    def _cycle_focus(self, direction: int) -> None:
        index = _FOCUS_ORDER.index(self.focus)
        self.focus = _FOCUS_ORDER[(index + direction) % len(_FOCUS_ORDER)]
        self._set_status(
            t("tui.status.focus_changed", pane=t(f"tui.focus.{self.focus}")),
            "info",
        )

    def _move_current_pane(self, delta: int) -> None:
        if self.focus == "files":
            if not self.file_changes:
                return
            self.selected_index = max(
                0, min(self.selected_index + delta, len(self.file_changes) - 1)
            )
            self._update_diff_preview(reset_scroll=True)
            return

        attr = "diff_scroll" if self.focus == "diff" else "message_scroll"
        setattr(self, attr, max(0, getattr(self, attr) + delta))

    def _page_current_pane(self, direction: int) -> None:
        if self._screen is None:
            return
        rows, cols = self._screen.getmaxyx()
        if rows < _MIN_ROWS or cols < _MIN_COLS:
            return

        body_height = rows - 4
        delta = max(1, body_height // 3) * direction
        if self.focus == "files":
            self._move_current_pane(delta)
            return

        attr = "diff_scroll" if self.focus == "diff" else "message_scroll"
        setattr(self, attr, max(0, getattr(self, attr) + delta))

    def refresh_snapshot(self, *, preserve_selection: bool = True) -> None:
        selected_path = self.selected_change.path if preserve_selection and self.selected_change else None
        self.snapshot = self.git.snapshot()
        self.file_changes = self.git.file_changes()

        if not self.file_changes:
            self.selected_index = 0
            self.file_scroll = 0
            self.diff_text = t("tui.empty.no_files")
            return

        if selected_path:
            for index, change in enumerate(self.file_changes):
                if change.path == selected_path:
                    self.selected_index = index
                    break
            else:
                self.selected_index = min(self.selected_index, len(self.file_changes) - 1)
        else:
            self.selected_index = min(self.selected_index, len(self.file_changes) - 1)

        self._update_diff_preview(reset_scroll=True)

    def _update_diff_preview(self, *, reset_scroll: bool) -> None:
        change = self.selected_change
        if change is None:
            self.diff_text = t("tui.empty.no_file_selected")
            return
        self.diff_text = self.git.diff_for_file(change.path)
        if reset_scroll:
            self.diff_scroll = 0

    def _render_before_action(self, message: str) -> None:
        self._set_status(message, "info")
        self._render()

    def _generate_message(self) -> None:
        if not self.snapshot.has_any_changes:
            self._set_status(t("cli.log.no_local_changes"), "warn")
            return

        try:
            self._render_before_action(t("cli.log.building_context"))
            prompt_payload = build_generation_payload(
                self.settings,
                self.snapshot,
                token_model=self.options.token_model,
                token_encoding=self.options.token_encoding,
            )
            self._render_before_action(
                t(
                    "cli.log.requesting_commit_proposal",
                    provider=self.settings.provider,
                    model_name=self.settings.model_name,
                )
            )
            raw_response = request_commit_proposal(self.settings, prompt_payload)
            result = finalize_generation(raw_response, wip=self.options.wip)
        except (GitError, LLMError, LazyCommitError) as exc:
            self._set_status(str(exc), "error")
            return

        self.generated_message = result.final_message
        self.message_scroll = 0
        self._set_status(t("tui.status.generated"), "ok")

        try:
            record_generated_history(
                self.git,
                self.snapshot,
                result.final_message,
                self.settings,
            )
        except OSError as exc:
            self._set_status(t("cli.log.history_save_failed", error=exc), "warn")

        if self.options.copy:
            copy_result = copy_text(result.final_message)
            self._set_status(
                copy_result.detail,
                "ok" if copy_result.ok else "warn",
            )

    def _copy_message(self) -> None:
        if not self.generated_message.strip():
            self._set_status(t("tui.error.no_message"), "warn")
            return
        copy_result = copy_text(self.generated_message)
        self._set_status(copy_result.detail, "ok" if copy_result.ok else "warn")

    def _stage_all(self) -> None:
        try:
            self._render_before_action(t("cli.log.staging_all"))
            self.git.stage_all()
            self.refresh_snapshot()
        except GitError as exc:
            self._set_status(str(exc), "error")
            return
        self._set_status(t("tui.status.staged_all"), "ok")

    def _toggle_stage_selected(self) -> None:
        change = self.selected_change
        if change is None:
            self._set_status(t("tui.error.no_file_selected"), "warn")
            return

        try:
            if change.is_staged:
                self.git.unstage_file(change.path)
                status_message = t("tui.status.unstaged_file", path=change.path)
            else:
                self.git.stage_file(change.path)
                status_message = t("tui.status.staged_file", path=change.path)
            self.refresh_snapshot()
        except GitError as exc:
            self._set_status(str(exc), "error")
            return

        self._set_status(status_message, "ok")

    def _commit(self, *, push: bool) -> None:
        if not self.generated_message.strip():
            self._set_status(t("tui.error.no_message"), "warn")
            return

        try:
            self._render_before_action(t("cli.log.creating_commit"))
            result = apply_commit_message(
                self.git,
                self.generated_message,
                push=push,
                remote=self.options.remote,
                branch=self.options.branch,
            )
            self.refresh_snapshot(preserve_selection=False)
        except (GitError, LazyCommitError) as exc:
            self._set_status(str(exc), "error")
            return

        if push and result.push_output:
            self._set_status(
                _first_non_empty_line(result.push_output, t("tui.status.pushed")),
                "ok",
            )
            return

        self._set_status(
            _first_non_empty_line(result.commit_output, t("tui.status.committed")),
            "ok",
        )


def run_tui(
    settings: Settings,
    options: TUIOptions,
    *,
    git: GitClient | None = None,
) -> int:
    """Launch the interactive TUI and return the process exit code."""
    application = LazyCommitTUI(settings, options, git=git)
    return application.run()
