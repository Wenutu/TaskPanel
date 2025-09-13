#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TaskPanel - View (Corrected and Finalized, Refactored & Optimized)

This module handles all rendering logic using 'curses'.
OPTIMIZED to use model-defined log formatters, respecting MVC separation.
"""
import curses
import os
import time
from enum import Enum, auto
from textwrap import wrap
from typing import List, NamedTuple, Optional, Tuple

from .model import Status, Step, Task, TaskModel


# --- Data Structures & Constants ---
class ViewState:
    def __init__(self):
        self.top_row = 0
        self.selected_row = 0
        self.selected_col = 0
        self.debug_panel_visible = False
        self.left_most_step = 0
        self.log_scroll_offset = 0
        self.debug_scroll_offset = 0
        self.spinner_frame = 0
        self.log_cache = {}
        self.layout_dirty = True
        self.cached_layout: Optional[LayoutDimensions] = None


class LayoutDimensions(NamedTuple):
    max_name_len: int
    info_col_width: int
    step_col_width: int
    num_visible_steps: int
    task_list_h: int
    bottom_pane_h: int
    log_panel_w: int
    debug_panel_w: int


LOG_BUFFER_LINES = 200
TAIL_BUFFER_SIZE = 4096
MIN_APP_HEIGHT = 15
MAX_TASK_LIST_HEIGHT = 20
MIN_BOTTOM_PANE_H = 8
HEADER_ROWS = 4
SEPARATOR_ROWS = 1
INFO_COLUMN_WIDTH = 15
MIN_STEP_COLUMN_WIDTH = 15
TABLE_X_OFFSET = 1
COL_PADDING = 2
INTER_COL_SEPARATOR_WIDTH = 1
EMPTY_STEP_TEXT = " --- "
SCROLL_UP_INDICATOR = "[^ ... more]"
SCROLL_DOWN_INDICATOR = "[v ... more]"
SCROLL_INDICATOR_PADDING = 15
SPINNER_CHARS = "|/-\\"


class ColorPair(Enum):
    DEFAULT = 1
    HEADER = auto()
    PENDING = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILED = auto()
    SKIPPED = auto()
    SELECTED = auto()
    OUTPUT_HEADER = auto()
    TABLE_HEADER = auto()
    KILLED = auto()
    STDERR = auto()
    EMPTY_STEP = auto()


STATUS_COLOR_MAP = {
    Status.PENDING: ColorPair.PENDING,
    Status.RUNNING: ColorPair.RUNNING,
    Status.SUCCESS: ColorPair.SUCCESS,
    Status.FAILED: ColorPair.FAILED,
    Status.SKIPPED: ColorPair.SKIPPED,
    Status.KILLED: ColorPair.KILLED,
}


def format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return ""
    seconds = int(seconds)
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    if days > 0:
        return f"{days}d {hours:02d}h"
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    if minutes > 0:
        return f"{minutes:02d}:{secs:02d}"
    return f"{secs:02d}s"


def setup_colors():
    """
    Set up color pairs for the application using a universal scheme
    that works on both light and dark backgrounds.
    """
    curses.start_color()
    curses.use_default_colors()

    # --- Universal Color Scheme ---
    # This scheme uses high-contrast combinations that are legible
    # on both light and dark terminal backgrounds, removing the need
    # for background detection.
    default_fg = -1  # Use terminal's default foreground
    default_bg = -1  # Use terminal's default background (transparent)

    # Blue background with white text is a classic high-contrast choice.
    header_fg = curses.COLOR_WHITE
    header_bg = curses.COLOR_BLUE

    # Green background with black text for selections is highly visible.
    selected_fg = curses.COLOR_BLACK
    selected_bg = curses.COLOR_GREEN

    curses.init_pair(ColorPair.DEFAULT.value, default_fg, default_bg)
    curses.init_pair(ColorPair.HEADER.value, header_fg, header_bg)
    curses.init_pair(ColorPair.PENDING.value, curses.COLOR_YELLOW, default_bg)
    curses.init_pair(ColorPair.RUNNING.value, curses.COLOR_CYAN, default_bg)
    curses.init_pair(ColorPair.SUCCESS.value, curses.COLOR_GREEN, default_bg)
    curses.init_pair(ColorPair.FAILED.value, curses.COLOR_RED, default_bg)
    curses.init_pair(ColorPair.SKIPPED.value, curses.COLOR_BLUE, default_bg)
    curses.init_pair(ColorPair.SELECTED.value, selected_fg, selected_bg)
    curses.init_pair(ColorPair.OUTPUT_HEADER.value, curses.COLOR_BLUE, default_bg)
    # Use the same style for table headers as the main header for consistency.
    curses.init_pair(ColorPair.TABLE_HEADER.value, header_fg, header_bg)
    curses.init_pair(ColorPair.KILLED.value, curses.COLOR_MAGENTA, default_bg)
    curses.init_pair(ColorPair.STDERR.value, curses.COLOR_RED, default_bg)
    # Use default color for empty steps, but dimmed.
    curses.init_pair(ColorPair.EMPTY_STEP.value, default_fg, default_bg)


def get_status_color(status: Status):
    return curses.color_pair(STATUS_COLOR_MAP.get(status, ColorPair.DEFAULT).value)


def _tail_file(filename: str, num_lines: int) -> List[str]:
    if not os.path.exists(filename):
        return []
    try:
        with open(filename, "rb") as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            if file_size == 0:
                return []
            buffer_size = TAIL_BUFFER_SIZE
            lines_found = 0
            block_num = 0
            while lines_found < num_lines and file_size > 0:
                block_num += 1
                seek_pos = file_size - (block_num * buffer_size)
                if seek_pos < 0:
                    seek_pos = 0
                f.seek(seek_pos, os.SEEK_SET)
                buffer = f.read(buffer_size)
                lines_found += buffer.count(b"\n")
                if seek_pos == 0:
                    break
            f.seek(
                file_size - (block_num * buffer_size)
                if file_size > (block_num * buffer_size)
                else 0
            )
            return [
                line.decode("utf-8", errors="replace") + "\n"
                for line in f.read().splitlines()[-num_lines:]
            ]
    except (IOError, OSError) as e:
        return [f"[Error tailing log '{filename}': {e}]\n"]


def read_log_files(step: Optional[Step]) -> List[Tuple[str, ColorPair]]:
    if not step:
        return []
    all_lines: List[Tuple[str, ColorPair]] = []
    stdout = _tail_file(step.log_path_stdout, LOG_BUFFER_LINES)
    stderr = _tail_file(step.log_path_stderr, LOG_BUFFER_LINES)
    if stdout:
        all_lines.append(("[STDOUT]\n", ColorPair.OUTPUT_HEADER))
        all_lines.extend([(line, ColorPair.DEFAULT) for line in stdout])
    if stderr:
        all_lines.append(("\n[STDERR]\n", ColorPair.STDERR))
        all_lines.extend([(line, ColorPair.STDERR) for line in stderr])
    return all_lines[-LOG_BUFFER_LINES:]


def calculate_layout_dimensions(
    w: int, model: TaskModel, h: int, debug_visible: bool
) -> LayoutDimensions:
    content_h = h - (HEADER_ROWS + SEPARATOR_ROWS)
    task_list_h = max(0, min(MAX_TASK_LIST_HEIGHT, content_h - MIN_BOTTOM_PANE_H))
    bottom_pane_h = max(0, content_h - task_list_h)
    log_panel_w = w // 2 if debug_visible else w
    debug_panel_w = (
        max(0, w - log_panel_w - INTER_COL_SEPARATOR_WIDTH) if debug_visible else 0
    )
    if not model.tasks:
        return LayoutDimensions(
            10,
            INFO_COLUMN_WIDTH,
            MIN_STEP_COLUMN_WIDTH,
            1,
            task_list_h,
            bottom_pane_h,
            log_panel_w,
            debug_panel_w,
        )
    max_name = max([len(t.name) for t in model.tasks] + [len(model.dynamic_header[0])])
    step_headers = model.dynamic_header[2:]
    step_w = (
        max([len(h) for h in step_headers] + [MIN_STEP_COLUMN_WIDTH])
        if step_headers
        else MIN_STEP_COLUMN_WIDTH
    )
    step_w += COL_PADDING
    steps_start_x = (
        TABLE_X_OFFSET
        + max_name
        + COL_PADDING
        + INFO_COLUMN_WIDTH
        + INTER_COL_SEPARATOR_WIDTH
    )
    num_visible = max(1, (w - steps_start_x) // step_w)
    return LayoutDimensions(
        max_name,
        INFO_COLUMN_WIDTH,
        step_w,
        num_visible,
        task_list_h,
        bottom_pane_h,
        log_panel_w,
        debug_panel_w,
    )


def _safe_addstr(stdscr, y, x, text, attr=0):
    try:
        h, w = stdscr.getmaxyx()
        if y < h and 0 <= x < w:
            stdscr.addstr(y, x, text[: w - x], attr)
    except curses.error:
        pass


def _draw_header(stdscr, w: int, title: str, is_search_mode: bool):
    help_text = (
        "SEARCH MODE: Type to filter. ESC to clear/exit. ENTER to confirm."
        if is_search_mode
        else "ARROWS:Nav | /:Search | r:Rerun | k:Kill | [/]:Log | {}:Dbg | d:Debug | q:Quit"
    )
    header_attr = curses.color_pair(ColorPair.HEADER.value)
    _safe_addstr(stdscr, 0, 0, title.ljust(w), header_attr)
    _safe_addstr(stdscr, 1, 0, help_text.ljust(w), header_attr)


def _draw_task_row(
    stdscr,
    y: int,
    task: Task,
    is_selected: bool,
    vs: ViewState,
    layout: LayoutDimensions,
):
    _safe_addstr(
        stdscr,
        y,
        TABLE_X_OFFSET,
        task.name.ljust(layout.max_name_len),
        curses.A_REVERSE if is_selected else 0,
    )
    info_x = TABLE_X_OFFSET + layout.max_name_len + COL_PADDING
    lines = task.info.splitlines()
    info_line = (lines[0] if lines else "").strip()
    if len(info_line) > layout.info_col_width - 3:
        info_line = info_line[: layout.info_col_width - 3]
    if len(lines) > 1 or len(info_line) > layout.info_col_width - 3:
        info_line = info_line + "..."
    info_attr = (
        curses.color_pair(ColorPair.SELECTED.value)
        if is_selected and vs.selected_col == -1
        else 0
    )
    _safe_addstr(stdscr, y, info_x, info_line.ljust(layout.info_col_width), info_attr)
    for i in range(layout.num_visible_steps):
        step_idx = vs.left_most_step + i
        if step_idx >= len(task.steps):
            break
        step = task.steps[step_idx]
        start_x = (
            info_x
            + layout.info_col_width
            + INTER_COL_SEPARATOR_WIDTH
            + (i * layout.step_col_width)
        )
        is_sel_col = is_selected and step_idx == vs.selected_col
        attr, text = (0, "")
        if step:
            attr = get_status_color(step.status)
            text = f" {step.status.value} "
            if step.status == Status.RUNNING:
                spinner_char = SPINNER_CHARS[vs.spinner_frame % len(SPINNER_CHARS)]
                timer_str = format_duration(
                    time.time() - step.start_time if step.start_time else None
                )
                text = f" {spinner_char} {timer_str} "
        else:
            attr = curses.color_pair(ColorPair.EMPTY_STEP.value) | curses.A_DIM
            text = EMPTY_STEP_TEXT
        if is_sel_col:
            attr = curses.color_pair(ColorPair.SELECTED.value)
        _safe_addstr(stdscr, y, start_x, text.center(layout.step_col_width), attr)


def _draw_task_table(
    stdscr,
    model: TaskModel,
    vs: ViewState,
    filtered_indices: List[int],
    layout: LayoutDimensions,
):
    header_y = HEADER_ROWS - 1
    table_header_attr = curses.color_pair(ColorPair.TABLE_HEADER.value)
    _safe_addstr(
        stdscr,
        header_y,
        TABLE_X_OFFSET,
        model.dynamic_header[0].center(layout.max_name_len),
        table_header_attr,
    )
    info_x = TABLE_X_OFFSET + layout.max_name_len + COL_PADDING
    _safe_addstr(
        stdscr,
        header_y,
        info_x,
        model.dynamic_header[1].center(layout.info_col_width),
        table_header_attr,
    )
    for i in range(layout.num_visible_steps):
        header_idx = vs.left_most_step + i + 2
        if header_idx >= len(model.dynamic_header):
            break
        start_x = (
            info_x
            + layout.info_col_width
            + INTER_COL_SEPARATOR_WIDTH
            + (i * layout.step_col_width)
        )
        _safe_addstr(
            stdscr,
            header_y,
            start_x,
            model.dynamic_header[header_idx].center(layout.step_col_width),
            table_header_attr,
        )
    visible_indices = filtered_indices[vs.top_row : vs.top_row + layout.task_list_h]
    for i, original_index in enumerate(visible_indices):
        task = model.tasks[original_index]
        is_selected = i + vs.top_row == vs.selected_row
        _draw_task_row(stdscr, HEADER_ROWS + i, task, is_selected, vs, layout)


def _get_log_file_stats(
    step: Optional[Step],
) -> Tuple[Optional[float], Optional[int], Optional[float], Optional[int]]:
    if not step:
        return None, None, None, None
    mtime1, size1, mtime2, size2 = None, None, None, None
    try:
        if os.path.exists(step.log_path_stdout):
            stat = os.stat(step.log_path_stdout)
            mtime1, size1 = stat.st_mtime, stat.st_size
        if os.path.exists(step.log_path_stderr):
            stat = os.stat(step.log_path_stderr)
            mtime2, size2 = stat.st_mtime, stat.st_size
    except OSError:
        pass
    return mtime1, size1, mtime2, size2


def _draw_bottom_pane(
    stdscr,
    y_start: int,
    model: TaskModel,
    vs: ViewState,
    filtered_indices: List[int],
    layout: LayoutDimensions,
    main_h: int,
):
    if layout.bottom_pane_h <= 1:
        return
    stdscr.hline(y_start - 1, 0, curses.ACS_HLINE, stdscr.getmaxyx()[1])
    if not filtered_indices:
        _safe_addstr(stdscr, y_start, 1, "No tasks match your search.", curses.A_BOLD)
        return
    task = model.tasks[filtered_indices[vs.selected_row]]
    step = (
        task.steps[vs.selected_col] if 0 <= vs.selected_col < len(task.steps) else None
    )
    if vs.selected_col == -1:
        _safe_addstr(
            stdscr,
            y_start,
            1,
            f"Full Info for: {task.name}"[: layout.log_panel_w - 2],
            curses.A_BOLD,
        )
        info_lines = [
            l
            for line in task.info.splitlines()
            for l in wrap(line, layout.log_panel_w - 4) or [""]
        ]
        for i, line in enumerate(info_lines[: layout.bottom_pane_h - 1]):
            _safe_addstr(stdscr, y_start + 1 + i, 2, line)
    elif step:
        header_text = (
            model.dynamic_header[vs.selected_col + 2]
            if vs.selected_col + 2 < len(model.dynamic_header)
            else ""
        )
        _safe_addstr(
            stdscr,
            y_start,
            1,
            f"Details for: {task.name} -> {header_text}"[: layout.log_panel_w - 2],
            curses.A_BOLD,
        )
        cache = vs.log_cache
        cache_key = (task.uid, vs.selected_col)
        mtime_out, size_out, mtime_err, size_err = _get_log_file_stats(step)
        if (
            cache.get("key") == cache_key
            and cache.get("mtime_out") == mtime_out
            and cache.get("size_out") == size_out
            and cache.get("mtime_err") == mtime_err
            and cache.get("size_err") == size_err
        ):
            output_lines = cache["content"]
        else:
            output_lines = read_log_files(step)
            vs.log_cache = {
                "key": cache_key,
                "content": output_lines,
                "mtime_out": mtime_out,
                "size_out": size_out,
                "mtime_err": mtime_err,
                "size_err": size_err,
            }

        log_content_width = max(1, layout.log_panel_w - 4)
        wrapped_log_lines = [
            (p, color)
            for line_text, color in output_lines
            for p in (
                wrap(
                    line_text.replace("\0", "?").expandtabs().rstrip("\n"),
                    log_content_width,
                )
                or [""]
            )
        ]

        max_scroll = max(0, len(wrapped_log_lines) - (layout.bottom_pane_h - 1))
        vs.log_scroll_offset = min(vs.log_scroll_offset, max_scroll)
        visible_lines = wrapped_log_lines[
            vs.log_scroll_offset : vs.log_scroll_offset + layout.bottom_pane_h - 1
        ]

        for idx, (line, color) in enumerate(visible_lines):
            attr = curses.color_pair(color.value) | (
                curses.A_BOLD if line.startswith("[") else 0
            )
            _safe_addstr(stdscr, y_start + 1 + idx, 2, line.replace("\0", "?"), attr)

        if vs.log_scroll_offset > 0:
            _safe_addstr(
                stdscr,
                y_start,
                max(2, layout.log_panel_w - SCROLL_INDICATOR_PADDING),
                SCROLL_UP_INDICATOR,
                curses.color_pair(ColorPair.PENDING.value),
            )
        if vs.log_scroll_offset < max_scroll:
            _safe_addstr(
                stdscr,
                main_h - 1,
                max(2, layout.log_panel_w - SCROLL_INDICATOR_PADDING),
                SCROLL_DOWN_INDICATOR,
                curses.color_pair(ColorPair.PENDING.value),
            )
    else:
        _safe_addstr(stdscr, y_start, 1, f"Details for: {task.name}", curses.A_BOLD)
        _safe_addstr(stdscr, y_start + 2, 2, "[No step defined for this column]")


def _draw_debug_pane(
    stdscr,
    y_start: int,
    model: TaskModel,
    vs: ViewState,
    filtered_indices: List[int],
    layout: LayoutDimensions,
    main_h: int,
):
    if not vs.debug_panel_visible or layout.debug_panel_w <= 1:
        return
    debug_x = layout.log_panel_w + 1 + INTER_COL_SEPARATOR_WIDTH
    stdscr.vline(
        y_start - 1, layout.log_panel_w + 1, curses.ACS_VLINE, layout.bottom_pane_h + 1
    )
    if not filtered_indices:
        _safe_addstr(stdscr, y_start, debug_x, "Debug Log", curses.A_BOLD)
        return
    task = model.tasks[filtered_indices[vs.selected_row]]
    step = (
        task.steps[vs.selected_col] if 0 <= vs.selected_col < len(task.steps) else None
    )
    panel_title, log_snapshot = "Debug Log", ["No task selected."]
    if step:
        header = (
            model.dynamic_header[vs.selected_col + 2]
            if vs.selected_col + 2 < len(model.dynamic_header)
            else ""
        )
        panel_title = f"Debug: {task.name} -> {header}"
        formatter = step.log_handler.formatter
        log_snapshot = [formatter.format(record) for record in step.log_handler.buffer]
    elif vs.selected_col == -1:
        panel_title, log_snapshot = f"Debug: {task.name}", [
            "Info column has no debug log."
        ]
    else:
        panel_title, log_snapshot = f"Debug: {task.name}", ["No step defined here."]
    _safe_addstr(
        stdscr, y_start, debug_x, panel_title[: layout.debug_panel_w - 1], curses.A_BOLD
    )
    wrapped_lines = [
        p
        for entry in log_snapshot
        for p in wrap(entry, max(1, layout.debug_panel_w - 2)) or [""]
    ]
    max_scroll = max(0, len(wrapped_lines) - (layout.bottom_pane_h - 1))
    vs.debug_scroll_offset = min(vs.debug_scroll_offset, max_scroll)
    visible_lines = wrapped_lines[
        vs.debug_scroll_offset : vs.debug_scroll_offset + layout.bottom_pane_h - 1
    ]
    for i, line in enumerate(visible_lines):
        _safe_addstr(stdscr, y_start + 1 + i, debug_x, line.replace("\0", "?"))
    if vs.debug_scroll_offset > 0:
        _safe_addstr(
            stdscr,
            y_start,
            max(debug_x, stdscr.getmaxyx()[1] - SCROLL_INDICATOR_PADDING),
            SCROLL_UP_INDICATOR,
            curses.color_pair(ColorPair.PENDING.value),
        )
    if vs.debug_scroll_offset < max_scroll:
        _safe_addstr(
            stdscr,
            main_h - 1,
            max(debug_x, stdscr.getmaxyx()[1] - SCROLL_INDICATOR_PADDING),
            SCROLL_DOWN_INDICATOR,
            curses.color_pair(ColorPair.PENDING.value),
        )


def draw_search_bar(stdscr, w: int, h: int, query: str):
    search_prompt = "Search: "
    bar_y = h - 1
    full_text = search_prompt + query
    header_attr = curses.color_pair(ColorPair.HEADER.value)
    stdscr.move(bar_y, 0)
    stdscr.clrtoeol()
    _safe_addstr(stdscr, bar_y, 0, full_text, header_attr)
    stdscr.move(bar_y, min(w - 1, len(full_text)))


def draw_ui(
    stdscr,
    model: TaskModel,
    vs: ViewState,
    filtered_indices: List[int],
    is_search_mode: bool,
    search_query: str,
    title: str,
):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    main_h = h - 1 if is_search_mode else h
    if main_h < MIN_APP_HEIGHT:
        _safe_addstr(stdscr, 0, 0, "Terminal too small.")
        stdscr.refresh()
        return
    if vs.layout_dirty:
        vs.cached_layout = calculate_layout_dimensions(
            w, model, main_h, vs.debug_panel_visible
        )
        vs.layout_dirty = False
    layout = vs.cached_layout
    with model.state_lock:
        y_bottom_pane_start = HEADER_ROWS + layout.task_list_h + SEPARATOR_ROWS
        _draw_header(stdscr, w, title, is_search_mode)
        _draw_task_table(stdscr, model, vs, filtered_indices, layout)
        _draw_bottom_pane(
            stdscr, y_bottom_pane_start, model, vs, filtered_indices, layout, main_h
        )
        _draw_debug_pane(
            stdscr, y_bottom_pane_start, model, vs, filtered_indices, layout, main_h
        )
    if is_search_mode:
        draw_search_bar(stdscr, w, h, search_query)
    stdscr.refresh()
