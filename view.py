#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TaskPanel - View (Optimized with High-Performance Log Reading)

This module is responsible for all rendering logic using 'curses'. It is the 'View'
in the MVC pattern, taking data from the Model and displaying it without any
knowledge of business logic or user input handling.

Key Improvements:
- Implements an efficient `_tail_file` function to read the end of log files,
  preventing high memory usage for large logs.
- Functions now expect structured `dataclass` objects (TaskModel, ViewState)
  for clearer and safer data handling.
"""
import curses
import os
from dataclasses import dataclass
from enum import Enum, auto
from textwrap import wrap
from typing import List, Tuple

# Type hints for data structures from other modules
from model import Status, TaskModel

# --- Data Structures & Constants ---
@dataclass
class ViewState:
    """A structured container for all UI-related state."""
    top_row: int = 0
    selected_row: int = 0
    selected_col: int = 0
    debug_panel_visible: bool = False
    left_most_step: int = 0
    log_scroll_offset: int = 0
    debug_scroll_offset: int = 0
    
LOG_BUFFER_LINES = 200  # Number of log lines to keep in memory and display.
MIN_MAIN_HEIGHT = 10    # Minimum terminal height for the main task view.
FIXED_DEBUG_HEIGHT = 12 # Fixed height for the debug panel.

# --- Enum for Type-Safe Color Pair Management ---
class ColorPair(Enum):
    """Enumeration for curses color pairs for improved readability."""
    DEFAULT = 1; HEADER = auto(); PENDING = auto(); RUNNING = auto()
    SUCCESS = auto(); FAILED = auto(); SKIPPED = auto(); SELECTED = auto()
    OUTPUT_HEADER = auto(); TABLE_HEADER = auto(); KILLED = auto(); STDERR = auto()

# Mapping from our Status Enum to our ColorPair Enum
STATUS_COLOR_MAP = {
    Status.PENDING: ColorPair.PENDING, Status.RUNNING: ColorPair.RUNNING,
    Status.SUCCESS: ColorPair.SUCCESS, Status.FAILED: ColorPair.FAILED,
    Status.SKIPPED: ColorPair.SKIPPED, Status.KILLED: ColorPair.KILLED,
}

def setup_colors():
    """Initializes all color pairs used by the application."""
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
    """Returns the curses color pair attribute for a given Status."""
    color_enum = STATUS_COLOR_MAP.get(status, ColorPair.DEFAULT)
    return curses.color_pair(color_enum.value)

def _tail_file(filename: str, num_lines: int) -> List[str]:
    """
    Efficiently reads the last `num_lines` from a file without loading the whole
    file into memory. Ideal for large log files.
    """
    if not os.path.exists(filename): return []
    try:
        with open(filename, "rb") as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            if file_size == 0: return []

            buffer_size = 4096
            lines_found = 0
            block_num = 0
            
            while lines_found < num_lines and file_size > 0:
                block_num += 1
                seek_pos = file_size - (block_num * buffer_size)
                if seek_pos < 0: seek_pos = 0
                
                f.seek(seek_pos, os.SEEK_SET)
                buffer = f.read(buffer_size)
                lines_found += buffer.count(b'\n')

                if seek_pos == 0: break
            
            f.seek(file_size - (block_num * buffer_size) if file_size > (block_num * buffer_size) else 0)
            last_lines_bytes = f.read().splitlines()[-num_lines:]
            return [line.decode('utf-8', errors='replace') + '\n' for line in last_lines_bytes]
    except Exception:
        return [f"[Error tailing log: {filename}]\n"]


def read_log_files(stdout_path: str, stderr_path: str) -> List[Tuple[str, ColorPair]]:
    """
    Reads the tail of stdout/stderr log files, tags lines by stream, and merges them.
    Returns a list of tuples: (line_text, color_pair_enum).
    """
    all_lines = []
    stdout_content = _tail_file(stdout_path, LOG_BUFFER_LINES)
    stderr_content = _tail_file(stderr_path, LOG_BUFFER_LINES)

    if stdout_content:
        all_lines.append(("[STDOUT]\n", ColorPair.OUTPUT_HEADER))
        all_lines.extend([(line, ColorPair.DEFAULT) for line in stdout_content])
    if stderr_content:
        all_lines.append(("[STDERR]\n", ColorPair.STDERR))
        all_lines.extend([(line, ColorPair.STDERR) for line in stderr_content])
    
    # This just combines the tails, it does not interleave them by timestamp.
    # For a simple log viewer, this is often sufficient.
    return all_lines[-LOG_BUFFER_LINES:]


def calculate_layout_dimensions(w: int, model: TaskModel, h: int, debug_panel_visible: bool) -> dict:
    """
    Calculates all dynamic UI dimensions. This is the single source of truth for layout.
    """
    debug_panel_active = debug_panel_visible and h >= MIN_MAIN_HEIGHT + FIXED_DEBUG_HEIGHT
    debug_panel_h = FIXED_DEBUG_HEIGHT if debug_panel_active else 0
    main_area_h = h - debug_panel_h
    task_list_h = main_area_h - 4 - 3 # Main height minus header/footer lines

    if not model.tasks:
        # Provide default values for an empty task list.
        return {'max_name_len': 10, 'info_col_width': 20, 'step_col_width': 12, 'num_visible_steps': 1, 'task_list_h': task_list_h, 'main_area_h': main_area_h, 'debug_panel_h': debug_panel_h, 'debug_panel_active': debug_panel_active}

    max_name_len = max([len(t.name) for t in model.tasks] + [len(model.dynamic_header[0])])
    info_col_w = 20
    step_col_w = max([len(h) for h in model.dynamic_header[2:]] + [12]) + 2 if len(model.dynamic_header) > 2 else 12
    steps_start_x = 1 + max_name_len + 2 + info_col_w + 3
    num_visible = max(1, (w - steps_start_x) // step_col_w)
    
    return {
        'max_name_len': max_name_len, 'info_col_width': info_col_w,
        'step_col_width': step_col_w, 'num_visible_steps': num_visible,
        'task_list_h': task_list_h, 'main_area_h': main_area_h,
        'debug_panel_h': debug_panel_h, 'debug_panel_active': debug_panel_active
    }


def draw_ui(stdscr, model: TaskModel, view_state: ViewState):
    """Draws the entire terminal UI based on the current model and view state."""
    stdscr.erase(); h, w = stdscr.getmaxyx()
    if h < 8: stdscr.addstr(0, 0, "Terminal too small."); stdscr.refresh(); return
    
    layout = calculate_layout_dimensions(w, model, h, view_state.debug_panel_visible)
    main_area_h, debug_panel_active = layout['main_area_h'], layout['debug_panel_active']

    # --- Draw Headers ---
    warning_message = " (Debug hidden: terminal too small)" if view_state.debug_panel_visible and not debug_panel_active else ""
    help_text = "ARROWS: Nav | r: Rerun | k: Kill | [/]: Log Scroll | {}/}: Dbg Scroll | d: Debug | q: Quit" + warning_message
    stdscr.attron(curses.color_pair(ColorPair.HEADER.value)); stdscr.addstr(0, 0, "TaskPanel".ljust(w)); stdscr.addstr(1, 0, help_text.ljust(w)); stdscr.attroff(curses.color_pair(ColorPair.HEADER.value))
    
    with model.state_lock:
        if not model.tasks:
            if h > 3: stdscr.addstr(3, 1, "No tasks loaded.")
            stdscr.refresh(); return
        
        # --- Draw Table Header ---
        header_y, y_start = 3, 4
        if header_y < main_area_h:
            table_header_attr = curses.color_pair(ColorPair.TABLE_HEADER.value)
            stdscr.addstr(header_y, 1, model.dynamic_header[0].center(layout['max_name_len']), table_header_attr)
            info_header_x = 1 + layout['max_name_len'] + 2
            stdscr.addstr(header_y, info_header_x, model.dynamic_header[1].center(layout['info_col_width']), table_header_attr)
            for i in range(view_state.left_most_step, min(view_state.left_most_step + layout['num_visible_steps'], len(model.dynamic_header) - 2)):
                j = i - view_state.left_most_step
                start_x = info_header_x + layout['info_col_width'] + 3 + (j * layout['step_col_width'])
                if start_x + layout['step_col_width'] < w: stdscr.addstr(header_y, start_x, model.dynamic_header[i+2].center(layout['step_col_width']), table_header_attr)
        
        # --- Draw Task List ---
        last_drawn_y = y_start - 1
        for i in range(view_state.top_row, min(view_state.top_row + layout['task_list_h'], len(model.tasks))):
            draw_y = y_start + (i - view_state.top_row)
            if draw_y >= main_area_h: break
            task = model.tasks[i]
            
            stdscr.addstr(draw_y, 1, task.name.ljust(layout['max_name_len']), curses.A_REVERSE if i == view_state.selected_row else curses.A_NORMAL)
            
            info_text_x = 1 + layout['max_name_len'] + 2
            lines = task.info.splitlines()
            if lines:
                trunc_len = max(0, layout['info_col_width'] - 4)
                first = lines[0]
                if len(lines) > 1 or len(first) > trunc_len:
                    info_line = (first[:trunc_len] + " ...") if trunc_len > 0 else "..."
                else:
                    info_line = first
            else:
                info_line = ""
            info_attr = curses.color_pair(ColorPair.SELECTED.value) if (i == view_state.selected_row and view_state.selected_col == -1) else curses.A_NORMAL
            stdscr.addstr(draw_y, info_text_x, info_line[:layout['info_col_width']-1].ljust(layout['info_col_width']), info_attr)
            
            for j in range(view_state.left_most_step, min(view_state.left_most_step + layout['num_visible_steps'], len(task.steps))):
                step = task.steps[j]
                attr = curses.color_pair(ColorPair.SELECTED.value) if (i == view_state.selected_row and j == view_state.selected_col) else get_status_color(step.status)
                start_x = info_text_x + layout['info_col_width'] + 3 + ((j - view_state.left_most_step) * layout['step_col_width'])
                if start_x + layout['step_col_width'] < w: stdscr.addstr(draw_y, start_x, f" {step.status.value} ".center(layout['step_col_width']), attr)
            last_drawn_y = draw_y
            
        # --- Draw Log/Info Panel ---
        output_start_y = last_drawn_y + 2
        if output_start_y < main_area_h:
            stdscr.hline(output_start_y - 1, 0, curses.ACS_HLINE, w)
            task = model.tasks[view_state.selected_row]
            if view_state.selected_col == -1: # Info panel selected
                stdscr.addstr(output_start_y, 1, f"Full Info for: {task.name}", curses.A_BOLD)
                info_lines = [l for line in task.info.splitlines() for l in wrap(line, w-4, break_long_words=False) or ['']]
                for idx, line in enumerate(info_lines):
                    if output_start_y + 1 + idx < main_area_h: stdscr.addstr(output_start_y + 1 + idx, 2, line)
            elif view_state.selected_col < len(task.steps): # A step is selected
                step = task.steps[view_state.selected_col]
                header = model.dynamic_header[view_state.selected_col+2] if view_state.selected_col+2 < len(model.dynamic_header) else ""
                stdscr.addstr(output_start_y, 1, f"Details for: {task.name} -> {header}", curses.A_BOLD)
                pid_str = f"PID: {step.process.pid}" if step.process and hasattr(step.process, 'pid') else "PID: N/A"
                stdscr.addstr(output_start_y, w - len(pid_str) - 1, pid_str)
                
                output_lines = read_log_files(step.log_path_stdout, step.log_path_stderr)
                max_scroll = max(0, len(output_lines) - (main_area_h - output_start_y - 1))
                view_state.log_scroll_offset = min(view_state.log_scroll_offset, max_scroll) # Clamp scroll offset
                
                for idx, (line, color) in enumerate(output_lines[view_state.log_scroll_offset:]):
                    if output_start_y + 1 + idx < main_area_h:
                        attr = curses.color_pair(color.value) | (curses.A_BOLD if line.startswith('[') else 0)
                        stdscr.addstr(output_start_y + 1 + idx, 2, line.rstrip()[:w-3], attr)
                
                if view_state.log_scroll_offset > 0: stdscr.addstr(output_start_y, w - 15, "[^ ... more]", curses.color_pair(ColorPair.PENDING.value))
                if view_state.log_scroll_offset < max_scroll: stdscr.addstr(main_area_h - 1, w - 15, "[v ... more]", curses.color_pair(ColorPair.PENDING.value))

    # --- Draw Debug Panel ---
    if debug_panel_active:
        stdscr.hline(main_area_h, 0, curses.ACS_HLINE, w)
        with model.state_lock:
            task = model.tasks[view_state.selected_row]
            if 0 <= view_state.selected_col < len(task.steps):
                step = task.steps[view_state.selected_col]
                header = model.dynamic_header[view_state.selected_col+2] if view_state.selected_col+2 < len(model.dynamic_header) else ""
                panel_title, log_snapshot = f"Debug Log for {task.name} -> {header}", list(step.debug_log)
            else: panel_title, log_snapshot = f"Debug Log for {task.name}", ["Info column has no debug log."]
        stdscr.addstr(main_area_h + 1, 1, panel_title, curses.A_BOLD)
        
        visible_lines = layout['debug_panel_h'] - 2
        if visible_lines > 0:
            max_scroll = max(0, len(log_snapshot) - visible_lines)
            view_state.debug_scroll_offset = min(view_state.debug_scroll_offset, max_scroll)
            for i, entry in enumerate(log_snapshot[view_state.debug_scroll_offset : view_state.debug_scroll_offset + visible_lines]):
                if main_area_h + 2 + i < h: stdscr.addstr(main_area_h + 2 + i, 1, entry[:w-2])
            
            if view_state.debug_scroll_offset > 0: stdscr.addstr(main_area_h + 1, w - 15, "[^ ... more]", curses.color_pair(ColorPair.PENDING.value))
            if view_state.debug_scroll_offset < max_scroll: stdscr.addstr(h - 1, w - 15, "[v ... more]", curses.color_pair(ColorPair.PENDING.value))

    stdscr.refresh()