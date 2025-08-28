#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TaskPanel - View (Corrected and Finalized)

This module handles all rendering logic using 'curses'. It is the 'View' in the MVC
pattern. This version is hardened against boundary errors and features a dynamic
side-by-side layout for the log and debug panels, and contextual help text.
"""
import curses
import os
from enum import Enum, auto
from textwrap import wrap
from typing import List, Tuple

from model import Status, TaskModel

# --- Data Structures & Constants ---
class ViewState:
    """A standard class container for all UI-related state."""
    def __init__(self):
        self.top_row = 0; self.selected_row = 0; self.selected_col = 0
        self.debug_panel_visible = False; self.left_most_step = 0
        self.log_scroll_offset = 0; self.debug_scroll_offset = 0

# --- Layout Constants ---
LOG_BUFFER_LINES = 200      # Number of log lines to keep in memory
MIN_APP_HEIGHT = 15         # Minimum terminal height to run the app
MAX_TASK_LIST_HEIGHT = 20   # Max height for the task list pane
MIN_BOTTOM_PANE_H = 8       # Minimum height for the bottom pane
HEADER_ROWS = 4             # Number of rows in the header
SEPARATOR_ROWS = 1          # Number of rows for separators

# --- Color Management (Unchanged) ---
class ColorPair(Enum):
    DEFAULT = 1; HEADER = auto(); PENDING = auto(); RUNNING = auto()
    SUCCESS = auto(); FAILED = auto(); SKIPPED = auto(); SELECTED = auto()
    OUTPUT_HEADER = auto(); TABLE_HEADER = auto(); KILLED = auto(); STDERR = auto()

STATUS_COLOR_MAP = {
    Status.PENDING: ColorPair.PENDING, Status.RUNNING: ColorPair.RUNNING,
    Status.SUCCESS: ColorPair.SUCCESS, Status.FAILED: ColorPair.FAILED,
    Status.SKIPPED: ColorPair.SKIPPED, Status.KILLED: ColorPair.KILLED,
}

def setup_colors():
    curses.start_color(); curses.use_default_colors()
    curses.init_pair(ColorPair.DEFAULT.value, curses.COLOR_BLUE, -1)
    curses.init_pair(ColorPair.HEADER.value, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(ColorPair.PENDING.value, curses.COLOR_YELLOW, -1)
    curses.init_pair(ColorPair.RUNNING.value, curses.COLOR_CYAN, -1)
    curses.init_pair(ColorPair.SUCCESS.value, curses.COLOR_GREEN, -1)
    curses.init_pair(ColorPair.FAILED.value, curses.COLOR_RED, -1)
    curses.init_pair(ColorPair.SKIPPED.value, curses.COLOR_BLUE, -1)
    curses.init_pair(ColorPair.SELECTED.value, curses.COLOR_BLACK, curses.COLOR_GREEN)
    curses.init_pair(ColorPair.OUTPUT_HEADER.value, curses.COLOR_BLUE, -1)
    curses.init_pair(ColorPair.TABLE_HEADER.value, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(ColorPair.KILLED.value, curses.COLOR_MAGENTA, -1)
    curses.init_pair(ColorPair.STDERR.value, curses.COLOR_RED, -1)

def get_status_color(status: Status):
    return curses.color_pair(STATUS_COLOR_MAP.get(status, ColorPair.DEFAULT).value)

def _tail_file(filename: str, num_lines: int) -> List[str]:
    if not os.path.exists(filename): return []
    try:
        with open(filename, "rb") as f:
            f.seek(0, os.SEEK_END); file_size = f.tell()
            if file_size == 0: return []
            buffer_size=4096; lines_found=0; block_num=0
            while lines_found < num_lines and file_size > 0:
                block_num += 1; seek_pos = file_size - (block_num * buffer_size)
                if seek_pos < 0: seek_pos = 0
                f.seek(seek_pos, os.SEEK_SET); buffer = f.read(buffer_size)
                lines_found += buffer.count(b'\n')
                if seek_pos == 0: break
            f.seek(file_size - (block_num * buffer_size) if file_size > (block_num * buffer_size) else 0)
            return [line.decode('utf-8', errors='replace') + '\n' for line in f.read().splitlines()[-num_lines:]]
    except (IOError, OSError) as e: return [f"[Error tailing log '{filename}': {e}]\n"]

def read_log_files(stdout_path: str, stderr_path: str) -> List[Tuple[str, ColorPair]]:
    all_lines = []; stdout = _tail_file(stdout_path, LOG_BUFFER_LINES); stderr = _tail_file(stderr_path, LOG_BUFFER_LINES)
    if stdout: all_lines.append(("[STDOUT]\n", ColorPair.OUTPUT_HEADER)); all_lines.extend([(line, ColorPair.DEFAULT) for line in stdout])
    if stderr: all_lines.append(("[STDERR]\n", ColorPair.STDERR)); all_lines.extend([(line, ColorPair.STDERR) for line in stderr])
    return all_lines[-LOG_BUFFER_LINES:]

# --- Layout Calculation (Unchanged from previous fix) ---
def calculate_layout_dimensions(w: int, model: TaskModel, h: int, debug_panel_visible: bool) -> dict:
    total_fixed_rows = HEADER_ROWS + SEPARATOR_ROWS; content_h = h - total_fixed_rows
    task_list_potential_h = content_h - MIN_BOTTOM_PANE_H
    task_list_h = min(MAX_TASK_LIST_HEIGHT, task_list_potential_h)
    task_list_h = max(0, task_list_h)
    bottom_pane_h = content_h - task_list_h
    bottom_pane_h = max(0, bottom_pane_h)
    log_panel_w, debug_panel_w = 0, 0
    if debug_panel_visible: log_panel_w = w // 2; debug_panel_w = max(0, w - log_panel_w - 1)
    else: log_panel_w = w; debug_panel_w = 0
    if not model.tasks: return {'max_name_len': 10, 'info_col_width': 20, 'step_col_width': 12, 'num_visible_steps': 1, 'task_list_h': task_list_h, 'bottom_pane_h': bottom_pane_h, 'log_panel_w': log_panel_w, 'debug_panel_w': debug_panel_w}
    max_name_len = max([len(t.name) for t in model.tasks] + [len(model.dynamic_header[0])])
    info_col_w = 20; step_col_w = max([len(h) for h in model.dynamic_header[2:]] + [12]) + 2 if len(model.dynamic_header) > 2 else 12
    steps_start_x = 1 + max_name_len + 2 + info_col_w + 3
    num_visible = max(1, (w - steps_start_x) // step_col_w)
    return {'max_name_len': max_name_len, 'info_col_width': info_col_w, 'step_col_width': step_col_w, 'num_visible_steps': num_visible, 'task_list_h': task_list_h, 'bottom_pane_h': bottom_pane_h, 'log_panel_w': log_panel_w, 'debug_panel_w': debug_panel_w}

# --- Drawing Functions (Help text updated) ---
def draw_search_bar(stdscr, w: int, h: int, query: str):
    search_prompt = "Search: "; bar_y = h - 1; full_text = search_prompt + query
    try:
        stdscr.attron(curses.color_pair(ColorPair.HEADER.value)); stdscr.move(bar_y, 0)
        stdscr.clrtoeol(); stdscr.addstr(bar_y, 0, full_text[:w-1])
        stdscr.attroff(curses.color_pair(ColorPair.HEADER.value))
        cursor_x = min(w - 2, len(full_text)); stdscr.move(bar_y, cursor_x)
    except curses.error: pass

def draw_ui(stdscr, model: TaskModel, view_state: ViewState, 
            filtered_indices: List[int], is_search_mode: bool, search_query: str):
    stdscr.erase(); h, w = stdscr.getmaxyx()
    main_h = h - 1 if is_search_mode else h
    if main_h < MIN_APP_HEIGHT: stdscr.addstr(0, 0, "Terminal too small."); stdscr.refresh(); return
    
    layout = calculate_layout_dimensions(w, model, main_h, view_state.debug_panel_visible)
    
    # --- Draw Headers (Context-Aware) ---
    if is_search_mode:
        help_text = "SEARCH MODE: Type to filter. ESC to clear/exit. ENTER to confirm."
    else:
        help_text = "ARROWS:Nav | /:Search | r:Rerun | k:Kill | [/]:Log | {}:Dbg | d:Debug | q:Quit"
    stdscr.attron(curses.color_pair(ColorPair.HEADER.value)); stdscr.addstr(0, 0, "TaskPanel".ljust(w)); stdscr.addstr(1, 0, help_text.ljust(w)); stdscr.attroff(curses.color_pair(ColorPair.HEADER.value))
    
    with model.state_lock:
        y_start = HEADER_ROWS
        header_y = y_start - 1
        table_header_attr = curses.color_pair(ColorPair.TABLE_HEADER.value)
        stdscr.addstr(header_y, 1, model.dynamic_header[0].center(layout['max_name_len']), table_header_attr)
        info_header_x = 1 + layout['max_name_len'] + 2
        stdscr.addstr(header_y, info_header_x, model.dynamic_header[1].center(layout['info_col_width']), table_header_attr)
        for i in range(view_state.left_most_step, min(view_state.left_most_step + layout['num_visible_steps'], len(model.dynamic_header) - 2)):
            j = i - view_state.left_most_step; start_x = info_header_x + layout['info_col_width'] + 3 + (j * layout['step_col_width'])
            if start_x + layout['step_col_width'] <= w:
                stdscr.addstr(header_y, start_x, model.dynamic_header[i+2].center(layout['step_col_width']), table_header_attr)
        
        visible_task_rows = filtered_indices[view_state.top_row : view_state.top_row + layout['task_list_h']]
        for i, original_index in enumerate(visible_task_rows):
            draw_y = y_start + i; task = model.tasks[original_index]; is_selected_row = (i + view_state.top_row == view_state.selected_row)
            stdscr.addstr(draw_y, 1, task.name.ljust(layout['max_name_len']), curses.A_REVERSE if is_selected_row else curses.A_NORMAL)
            lines = task.info.splitlines()
            if lines:
                info_line = lines[0]
                max_width = layout['info_col_width'] - 3
                if len(lines) > 1:
                    info_line = (info_line[:max_width] + "...") if len(info_line) > max_width else (info_line + " ...")
                else:
                    if len(info_line) > max_width:
                        info_line = info_line[:max_width] + "..."
            else:
                info_line = ""
            info_attr = curses.color_pair(ColorPair.SELECTED.value) if (is_selected_row and view_state.selected_col == -1) else curses.A_NORMAL
            stdscr.addstr(draw_y, info_header_x, info_line.ljust(layout['info_col_width']), info_attr)
            for j in range(view_state.left_most_step, min(view_state.left_most_step + layout['num_visible_steps'], len(task.steps))):
                step = task.steps[j]; attr = curses.color_pair(ColorPair.SELECTED.value) if (is_selected_row and j == view_state.selected_col) else get_status_color(step.status)
                start_x = info_header_x + layout['info_col_width'] + 3 + ((j - view_state.left_most_step) * layout['step_col_width'])
                # FIX: Changed '<' to '<=' to correctly draw the last visible step status if it fits exactly.
                if start_x + layout['step_col_width'] <= w:
                    stdscr.addstr(draw_y, start_x, f" {step.status.value} ".center(layout['step_col_width']), attr)
            
        separator_y = y_start + layout['task_list_h']; output_start_y = separator_y + 1
        if layout['bottom_pane_h'] > 1:
            stdscr.hline(separator_y, 0, curses.ACS_HLINE, w)
            if not filtered_indices: stdscr.addstr(output_start_y, 1, "No tasks match your search.", curses.A_BOLD)
            else:
                original_task_index = filtered_indices[view_state.selected_row]; task = model.tasks[original_task_index]; log_w = layout['log_panel_w']
                if view_state.selected_col == -1:
                    stdscr.addstr(output_start_y, 1, f"Full Info for: {task.name}"[:log_w-2], curses.A_BOLD)
                    info_lines = [l for line in task.info.splitlines() for l in wrap(line, log_w-4, break_long_words=False) or ['']]
                    for idx, line in enumerate(info_lines[:layout['bottom_pane_h']-1]): stdscr.addstr(output_start_y + 1 + idx, 2, line)
                elif view_state.selected_col < len(task.steps):
                    step = task.steps[view_state.selected_col]; header = model.dynamic_header[view_state.selected_col+2] if view_state.selected_col+2 < len(model.dynamic_header) else ""
                    stdscr.addstr(output_start_y, 1, f"Details for: {task.name} -> {header}"[:log_w-2], curses.A_BOLD)
                    pid_str = f"PID: {step.process.pid}" if step.process and hasattr(step.process, 'pid') else "PID: N/A"
                    if len(pid_str) < log_w - 2: stdscr.addstr(output_start_y, log_w - len(pid_str) - 1, pid_str)
                    
                    output_lines = read_log_files(step.log_path_stdout, step.log_path_stderr)
                    wrapped_log_lines = []
                    log_content_width = max(1, log_w - 4) # Width available for text inside the panel
                    for line_text, color in output_lines:
                        wrapped_parts = wrap(line_text.rstrip('\n'), log_content_width) or ['']
                        for part in wrapped_parts:
                            wrapped_log_lines.append((part, color))

                    max_scroll = max(0, len(wrapped_log_lines) - (layout['bottom_pane_h'] - 1))
                    view_state.log_scroll_offset = min(view_state.log_scroll_offset, max_scroll)
                    
                    visible_lines = wrapped_log_lines[view_state.log_scroll_offset : view_state.log_scroll_offset + layout['bottom_pane_h'] - 1]
                    for idx, (line, color) in enumerate(visible_lines):
                        attr = curses.color_pair(color.value) | (curses.A_BOLD if line.startswith('[') else 0)
                        stdscr.addstr(output_start_y + 1 + idx, 2, line, attr)
                    
                    try:
                        if view_state.log_scroll_offset > 0: stdscr.addstr(output_start_y, max(2, log_w - 15), "[^ ... more]", curses.color_pair(ColorPair.PENDING.value))
                        if view_state.log_scroll_offset < max_scroll: stdscr.addstr(main_h - 1, max(2, log_w - 15), "[v ... more]", curses.color_pair(ColorPair.PENDING.value))
                    except curses.error: pass
            
            if view_state.debug_panel_visible and layout['debug_panel_w'] > 1:
                stdscr.vline(output_start_y, layout['log_panel_w'], curses.ACS_VLINE, layout['bottom_pane_h']); debug_w = layout['debug_panel_w']; debug_x = layout['log_panel_w'] + 2
                if not filtered_indices: panel_title, log_snapshot = "Debug Log", ["No task selected."]
                else:
                    original_task_index = filtered_indices[view_state.selected_row]; task = model.tasks[original_task_index]
                    if 0 <= view_state.selected_col < len(task.steps):
                        step = task.steps[view_state.selected_col]; header = model.dynamic_header[view_state.selected_col+2] if view_state.selected_col+2 < len(model.dynamic_header) else ""
                        panel_title, log_snapshot = f"Debug: {task.name} -> {header}", list(step.debug_log)
                    else: panel_title, log_snapshot = f"Debug: {task.name}", ["Info column has no debug log."]
                stdscr.addstr(output_start_y, debug_x - 1, panel_title[:debug_w-1], curses.A_BOLD)
                
                wrapped_debug_lines = []
                debug_content_width = max(1, debug_w - 2) # Width available for text
                for entry in log_snapshot:
                    wrapped_parts = wrap(entry, debug_content_width) or ['']
                    wrapped_debug_lines.extend(wrapped_parts)

                visible_lines_count = layout['bottom_pane_h'] - 1
                if visible_lines_count > 0:
                    max_scroll = max(0, len(wrapped_debug_lines) - visible_lines_count)
                    view_state.debug_scroll_offset = min(view_state.debug_scroll_offset, max_scroll)
                    visible_lines = wrapped_debug_lines[view_state.debug_scroll_offset : view_state.debug_scroll_offset + visible_lines_count]
                    for i, line in enumerate(visible_lines):
                        stdscr.addstr(output_start_y + 1 + i, debug_x - 1, line) # No slicing needed
                    
                    try:
                        if view_state.debug_scroll_offset > 0: stdscr.addstr(output_start_y, max(debug_x, w - 15), "[^...]", curses.color_pair(ColorPair.PENDING.value))
                        if view_state.debug_scroll_offset < max_scroll: stdscr.addstr(main_h - 1, max(debug_x, w - 15), "[v...]", curses.color_pair(ColorPair.PENDING.value))
                    except curses.error: pass
    
    if is_search_mode:
        draw_search_bar(stdscr, w, h, search_query)

    stdscr.refresh()