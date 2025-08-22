#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TaskPanel - View (Optimized for Separate, Colored Log Streams)

This module is responsible for all rendering logic using the 'curses' library.
It is the 'View' in the MVC pattern, taking data from the Model and displaying
it. It has no knowledge of business logic or user input handling.
"""
import curses
import os
from textwrap import wrap
from enum import Enum, auto

from model import Status # Import the Status Enum from the model

# --- Enum for Type-Safe Color Pair Management ---
class ColorPair(Enum):
    """Enumeration for curses color pairs for improved readability."""
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

# Mapping from Status Enum to ColorPair Enum
STATUS_COLOR_MAP = {
    Status.PENDING: ColorPair.PENDING,
    Status.RUNNING: ColorPair.RUNNING,
    Status.SUCCESS: ColorPair.SUCCESS,
    Status.FAILED: ColorPair.FAILED,
    Status.SKIPPED: ColorPair.SKIPPED,
    Status.KILLED: ColorPair.KILLED,
}

def get_status_color(status: Status):
    """Returns the curses color pair attribute for a given Status."""
    color_enum = STATUS_COLOR_MAP.get(status, ColorPair.DEFAULT)
    return curses.color_pair(color_enum.value)

def read_log_files(stdout_path, stderr_path, num_lines=200):
    """
    Reads the tail of stdout and stderr log files, tagging lines by stream.
    Returns a list of tuples: (line_text, color_pair_enum).
    """
    all_lines = []
    # Helper to read a file and tag its lines with a color
    def read_file(path, color, header):
        content = []
        try:
            if os.path.exists(path) and os.path.getsize(path) > 0:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    content.extend([(line, color) for line in f.readlines()])
        except Exception as e:
            content.append((f"[Error reading log: {e}]\n", ColorPair.FAILED))
        if content:
            all_lines.append((f"[{header}]\n", ColorPair.OUTPUT_HEADER if header == "STDOUT" else ColorPair.FAILED))
            all_lines.extend(content)

    read_file(stdout_path, ColorPair.DEFAULT, "STDOUT")
    read_file(stderr_path, ColorPair.STDERR, "STDERR")
    return all_lines[-num_lines:]

def calculate_layout_dimensions(w, model, h, debug_panel_visible) -> dict:
    """
    Calculates all dynamic UI dimensions. This is the single source of truth for layout.
    Returns a dictionary of layout metrics.
    """
    # --- Vertical Calculations ---
    MIN_MAIN_HEIGHT, FIXED_DEBUG_HEIGHT = 10, 12
    debug_panel_active = debug_panel_visible and h >= MIN_MAIN_HEIGHT + FIXED_DEBUG_HEIGHT
    debug_panel_h = FIXED_DEBUG_HEIGHT if debug_panel_active else 0
    main_area_h = h - debug_panel_h
    task_list_h = main_area_h - 4 - 3 # Height for task list (Header + Footer)

    # --- Horizontal Calculations ---
    if not model.tasks:
        return {'max_name_len': 10, 'info_col_width': 20, 'step_col_width': 12, 'num_visible_steps': 1, 'task_list_h': task_list_h, 'main_area_h': main_area_h, 'debug_panel_h': debug_panel_h, 'debug_panel_active': debug_panel_active}

    max_name_len = max([len(t['name']) for t in model.tasks] + [len(model.dynamic_header[0])])
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


def draw_ui(stdscr, model, view_state):
    """Draws the entire terminal UI, reading step logs from separate files."""
    stdscr.erase(); h, w = stdscr.getmaxyx()
    if h < 8: stdscr.addstr(0, 0, "Terminal too small."); stdscr.refresh(); return
    
    # Unpack view state for readability
    vs = view_state
    
    # Get all layout dimensions from the centralized function
    layout = calculate_layout_dimensions(w, model, h, vs['debug_panel_visible'])
    main_area_h, debug_panel_active = layout['main_area_h'], layout['debug_panel_active']

    # --- Draw Headers ---
    warning_message = " (Debug hidden: terminal too small)" if vs['debug_panel_visible'] and not debug_panel_active else ""
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
            for i in range(vs['left_most_step'], min(vs['left_most_step'] + layout['num_visible_steps'], len(model.dynamic_header) - 2)):
                j = i - vs['left_most_step']
                start_x = info_header_x + layout['info_col_width'] + 3 + (j * layout['step_col_width'])
                if start_x + layout['step_col_width'] < w: stdscr.addstr(header_y, start_x, model.dynamic_header[i+2].center(layout['step_col_width']), table_header_attr)
        
        # --- Draw Task List ---
        last_drawn_y = y_start - 1
        for i in range(vs['top_row'], min(vs['top_row'] + layout['task_list_h'], len(model.tasks))):
            draw_y = y_start + (i - vs['top_row'])
            if draw_y >= main_area_h: break
            task = model.tasks[i]
            
            stdscr.addstr(draw_y, 1, task["name"].ljust(layout['max_name_len']), curses.A_REVERSE if i == vs['selected_row'] else curses.A_NORMAL)
            
            info_text_x = 1 + layout['max_name_len'] + 2
            info_line = task.get('info', '').splitlines()[0] if task.get('info') else ''
            info_attr = curses.color_pair(ColorPair.SELECTED.value) if (i == vs['selected_row'] and vs['selected_col'] == -1) else curses.A_NORMAL
            stdscr.addstr(draw_y, info_text_x, info_line[:layout['info_col_width']-1].ljust(layout['info_col_width']), info_attr)
            
            for j in range(vs['left_most_step'], min(vs['left_most_step'] + layout['num_visible_steps'], len(task["steps"]))):
                step = task["steps"][j]
                attr = curses.color_pair(ColorPair.SELECTED.value) if (i == vs['selected_row'] and j == vs['selected_col']) else get_status_color(step["status"])
                start_x = info_text_x + layout['info_col_width'] + 3 + ((j - vs['left_most_step']) * layout['step_col_width'])
                if start_x + layout['step_col_width'] < w: stdscr.addstr(draw_y, start_x, f" {step['status'].value} ".center(layout['step_col_width']), attr)
            last_drawn_y = draw_y
            
        # --- Draw Log/Info Panel ---
        output_start_y = last_drawn_y + 2
        if output_start_y < main_area_h:
            stdscr.hline(output_start_y - 1, 0, curses.ACS_HLINE, w)
            task = model.tasks[vs['selected_row']]
            if vs['selected_col'] == -1: # Info panel selected
                stdscr.addstr(output_start_y, 1, f"Full Info for: {task['name']}", curses.A_BOLD)
                full_info_text = task.get('info', '')
                info_lines = [l for line in full_info_text.splitlines() for l in wrap(line, w-4, break_long_words=False) or ['']]
                for idx, line in enumerate(info_lines):
                    if output_start_y + 1 + idx < main_area_h: stdscr.addstr(output_start_y + 1 + idx, 2, line)
            elif vs['selected_col'] < len(task["steps"]): # A step is selected
                step = task["steps"][vs['selected_col']]
                header = model.dynamic_header[vs['selected_col']+2] if vs['selected_col']+2 < len(model.dynamic_header) else ""
                stdscr.addstr(output_start_y, 1, f"Details for: {task['name']} -> {header}", curses.A_BOLD)
                pid_str = f"PID: {step['process'].pid}" if step.get('process') and hasattr(step['process'], 'pid') else "PID: N/A"
                stdscr.addstr(output_start_y, w - len(pid_str) - 1, pid_str)
                
                output_lines = read_log_files(step['log_path_stdout'], step['log_path_stderr'])
                max_scroll = max(0, len(output_lines) - (main_area_h - output_start_y - 1))
                vs['log_scroll_offset'] = min(vs['log_scroll_offset'], max_scroll) # Clamp scroll offset
                
                for idx, (line, color) in enumerate(output_lines[vs['log_scroll_offset']:]):
                    if output_start_y + 1 + idx < main_area_h:
                        attr = curses.color_pair(color.value) | (curses.A_BOLD if line.startswith('[') else 0)
                        stdscr.addstr(output_start_y + 1 + idx, 2, line.rstrip()[:w-3], attr)
                
                if vs['log_scroll_offset'] > 0: stdscr.addstr(output_start_y, w - 15, "[^ ... more]", curses.color_pair(ColorPair.PENDING.value))
                if vs['log_scroll_offset'] < max_scroll: stdscr.addstr(main_area_h - 1, w - 15, "[v ... more]", curses.color_pair(ColorPair.PENDING.value))

    # --- Draw Debug Panel ---
    if debug_panel_active:
        stdscr.hline(main_area_h, 0, curses.ACS_HLINE, w)
        with model.state_lock:
            task = model.tasks[vs['selected_row']]
            if 0 <= vs['selected_col'] < len(task["steps"]):
                step = task["steps"][vs['selected_col']]
                header = model.dynamic_header[vs['selected_col']+2] if vs['selected_col']+2 < len(model.dynamic_header) else ""
                panel_title, log_snapshot = f"Debug Log for {task['name']} -> {header}", list(step["debug_log"])
            else: panel_title, log_snapshot = f"Debug Log for {task['name']}", ["Info column has no debug log."]
        stdscr.addstr(main_area_h + 1, 1, panel_title, curses.A_BOLD)
        
        visible_lines = layout['debug_panel_h'] - 2
        if visible_lines > 0:
            max_scroll = max(0, len(log_snapshot) - visible_lines)
            vs['debug_scroll_offset'] = min(vs['debug_scroll_offset'], max_scroll)
            for i, entry in enumerate(log_snapshot[vs['debug_scroll_offset'] : vs['debug_scroll_offset'] + visible_lines]):
                if main_area_h + 2 + i < h: stdscr.addstr(main_area_h + 2 + i, 1, entry[:w-2])
            
            if vs['debug_scroll_offset'] > 0: stdscr.addstr(main_area_h + 1, w - 15, "[^ ... more]", curses.color_pair(ColorPair.PENDING.value))
            if vs['debug_scroll_offset'] < max_scroll: stdscr.addstr(h - 1, w - 15, "[v ... more]", curses.color_pair(ColorPair.PENDING.value))

    stdscr.refresh()