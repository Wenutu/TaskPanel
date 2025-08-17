#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TaskPanel - View (Optimized for Separate, Colored Log Streams)
"""
import curses
import os
from textwrap import wrap

(COLOR_PAIR_DEFAULT, COLOR_PAIR_HEADER, COLOR_PAIR_PENDING, COLOR_PAIR_RUNNING,
 COLOR_PAIR_SUCCESS, COLOR_PAIR_FAILED, COLOR_PAIR_SKIPPED, COLOR_PAIR_SELECTED,
 COLOR_PAIR_OUTPUT_HEADER, COLOR_PAIR_TABLE_HEADER, COLOR_PAIR_KILLED, COLOR_PAIR_STDERR) = range(1, 13)

def setup_colors():
    curses.start_color(); curses.use_default_colors()
    curses.init_pair(COLOR_PAIR_DEFAULT, curses.COLOR_WHITE, -1); curses.init_pair(COLOR_PAIR_HEADER, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(COLOR_PAIR_PENDING, curses.COLOR_YELLOW, -1); curses.init_pair(COLOR_PAIR_RUNNING, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_PAIR_SUCCESS, curses.COLOR_GREEN, -1); curses.init_pair(COLOR_PAIR_FAILED, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_PAIR_SKIPPED, curses.COLOR_BLUE, -1); curses.init_pair(COLOR_PAIR_SELECTED, curses.COLOR_BLACK, curses.COLOR_GREEN)
    curses.init_pair(COLOR_PAIR_OUTPUT_HEADER, curses.COLOR_YELLOW, -1); curses.init_pair(COLOR_PAIR_TABLE_HEADER, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(COLOR_PAIR_KILLED, curses.COLOR_MAGENTA, -1); curses.init_pair(COLOR_PAIR_STDERR, curses.COLOR_RED, -1)

def get_status_color(status):
    return curses.color_pair({"PENDING": COLOR_PAIR_PENDING, "RUNNING": COLOR_PAIR_RUNNING, "SUCCESS": COLOR_PAIR_SUCCESS, "FAILED": COLOR_PAIR_FAILED,
                             "SKIPPED": COLOR_PAIR_SKIPPED, "KILLED": COLOR_PAIR_KILLED}.get(status, COLOR_PAIR_DEFAULT))

def read_log_files(stdout_path, stderr_path, num_lines=200):
    """
    Reads the tail of both stdout and stderr log files.
    Returns a list of tuples: (line, color_pair_id).
    Headers are added if their respective streams have content.
    """
    all_lines = []
    stdout_content = []
    stderr_content = []

    try:
        if os.path.exists(stdout_path) and os.path.getsize(stdout_path) > 0:
            with open(stdout_path, 'r', encoding='utf-8', errors='replace') as f:
                stdout_content.extend([(line, COLOR_PAIR_DEFAULT) for line in f.readlines()])
    except Exception as e:
        stdout_content.append((f"[Error reading stdout: {e}]\n", COLOR_PAIR_FAILED))

    try:
        if os.path.exists( stderr_path) and os.path.getsize(stderr_path) > 0:
            with open(stderr_path, 'r', encoding='utf-8', errors='replace') as f:
                stderr_content.extend([(line, COLOR_PAIR_STDERR) for line in f.readlines()])
    except Exception as e:
        stderr_content.append((f"[Error reading stderr: {e}]\n", COLOR_PAIR_FAILED))
    
    if stdout_content:
        all_lines.append(("[STDOUT]\n", COLOR_PAIR_OUTPUT_HEADER))
        all_lines.extend(stdout_content)

    if stderr_content:
        all_lines.append(("[STDERR]\n", COLOR_PAIR_FAILED))
        all_lines.extend(stderr_content)
        
    return all_lines[-num_lines:]

def calculate_layout_dimensions(w, model, h, debug_panel_visible):
    """
    Calculates all dynamic UI dimensions. This is the single source of truth for layout.
    """
    # ### FIX: All layout calculations, including vertical ones, are now centralized here. ###
    
    # --- Vertical Calculations ---
    MIN_MAIN_HEIGHT = 10
    FIXED_DEBUG_HEIGHT = 12
    debug_panel_active = debug_panel_visible
    # Check if there's enough space for the debug panel at all
    if debug_panel_visible and h < MIN_MAIN_HEIGHT + FIXED_DEBUG_HEIGHT:
        debug_panel_active = False
        
    debug_panel_height = FIXED_DEBUG_HEIGHT if debug_panel_active else 0
    main_area_h = h - debug_panel_height
    y_start = 4 # Start drawing tasks below the header
    task_list_h = main_area_h - y_start - 3 # Height available for the task list itself
    
    # --- Horizontal Calculations ---
    if not model.tasks:
        return 10, 20, 12, 1, task_list_h

    max_name_len = max([len(t['name']) for t in model.tasks] + [len(model.dynamic_header[0])])
    info_col_width = 20
    step_col_width = max([len(h) for h in model.dynamic_header[2:]] + [12]) + 2 if len(model.dynamic_header) > 2 else 12
    
    info_header_x = 1 + max_name_len + 2 + info_col_width + 3
    available_width_for_steps = w - info_header_x
    num_visible_steps = max(1, available_width_for_steps // step_col_width)
    
    return max_name_len, info_col_width, step_col_width, num_visible_steps, task_list_h


def draw_ui(stdscr, model, view_state):
    """Draws the entire terminal UI, reading step logs from separate files."""
    stdscr.erase(); h, w = stdscr.getmaxyx()
    if h < 8: stdscr.addstr(0, 0, "Terminal too small."); stdscr.refresh(); return
    
    top_row, selected_row, selected_col = view_state['top_row'], view_state['selected_row'], view_state['selected_col']
    left_most_step = view_state['left_most_step']
    log_scroll_offset = view_state['log_scroll_offset']
    debug_scroll_offset = view_state['debug_scroll_offset']
    debug_panel_visible = view_state['debug_panel_visible']

    MIN_MAIN_HEIGHT = 10; FIXED_DEBUG_HEIGHT = 12
    debug_panel_active = debug_panel_visible; warning_message = ""
    if debug_panel_visible and h < MIN_MAIN_HEIGHT + FIXED_DEBUG_HEIGHT:
        debug_panel_active = False; warning_message = " (Debug hidden: terminal too small)"
    debug_panel_height = FIXED_DEBUG_HEIGHT if debug_panel_active else 0
    main_area_h = h - debug_panel_height

    help_text = "ARROWS: Nav | r: Rerun | k: Kill | [/]: Log Scroll | {}/}: Dbg Scroll | d: Debug | q: Quit"
    help_text += warning_message
    stdscr.attron(curses.color_pair(COLOR_PAIR_HEADER)); stdscr.addstr(0, 0, "TaskPanel".ljust(w)); stdscr.addstr(1, 0, help_text.ljust(w)); stdscr.attroff(curses.color_pair(COLOR_PAIR_HEADER))
    
    with model.state_lock:
        if not model.tasks:
            if h > 3: stdscr.addstr(3, 1, "No tasks loaded.")
            stdscr.refresh(); return
        
        max_name_len, info_col_width, step_col_width, num_visible_steps, task_list_h = \
            calculate_layout_dimensions(w, model, h, debug_panel_visible)
        
        header_y, y_start = 3, 4
        
        if header_y < main_area_h:
            stdscr.attron(curses.color_pair(COLOR_PAIR_TABLE_HEADER)); stdscr.addstr(header_y, 1, model.dynamic_header[0].center(max_name_len)); stdscr.attroff(curses.color_pair(COLOR_PAIR_TABLE_HEADER))
            info_header_x = 1 + max_name_len + 2
            stdscr.attron(curses.color_pair(COLOR_PAIR_TABLE_HEADER)); stdscr.addstr(header_y, info_header_x, model.dynamic_header[1].center(info_col_width)); stdscr.attroff(curses.color_pair(COLOR_PAIR_TABLE_HEADER))
            
            for i in range(left_most_step, min(left_most_step + num_visible_steps, len(model.dynamic_header) - 2)):
                j = i - left_most_step
                col_name = model.dynamic_header[i + 2]
                start_x = info_header_x + info_col_width + 3 + (j * step_col_width)
                if start_x + step_col_width < w: stdscr.attron(curses.color_pair(COLOR_PAIR_TABLE_HEADER)); stdscr.addstr(header_y, start_x, col_name.center(step_col_width)); stdscr.attroff(curses.color_pair(COLOR_PAIR_TABLE_HEADER))
        
        last_drawn_y = y_start - 1
        
        for i in range(top_row, min(top_row + task_list_h, len(model.tasks))):
            draw_y = y_start + (i - top_row)
            if draw_y >= main_area_h: break
            task = model.tasks[i]
            
            stdscr.addstr(draw_y, 1, task["name"].ljust(max_name_len), curses.A_REVERSE if i == selected_row else curses.A_NORMAL)
            
            info_text_x = 1 + max_name_len + 2
            info_text = task.get('info', '')
            info_attr = curses.color_pair(COLOR_PAIR_SELECTED) if (i == selected_row and selected_col == -1) else curses.A_NORMAL
            stdscr.addstr(draw_y, info_text_x, info_text[:info_col_width-1].ljust(info_col_width), info_attr)
            
            for j in range(left_most_step, min(left_most_step + num_visible_steps, len(task["steps"]))):
                on_screen_col_idx = j - left_most_step
                step = task["steps"][j]
                attr = curses.color_pair(COLOR_PAIR_SELECTED) if (i == selected_row and j == selected_col) else get_status_color(step["status"])
                start_x = info_text_x + info_col_width + 3 + (on_screen_col_idx * step_col_width)
                if start_x + step_col_width < w: stdscr.addstr(draw_y, start_x, f" {step['status']} ".center(step_col_width), attr)
            last_drawn_y = draw_y
            
        output_start_y = last_drawn_y + 2
        if output_start_y < main_area_h:
            stdscr.hline(output_start_y - 1, 0, curses.ACS_HLINE, w)
            if model.tasks and selected_row < len(model.tasks):
                task = model.tasks[selected_row]
                if selected_col == -1:
                    stdscr.addstr(output_start_y, 1, f"Full Info for: {task['name']}", curses.A_BOLD)
                    full_info_text = task.get('info', '')
                    info_lines_final = []
                    for line in full_info_text.splitlines():
                        wrapped = wrap(line, w - 4, break_long_words=False, replace_whitespace=False)
                        info_lines_final.extend(wrapped if wrapped else [''])
                    for idx, line in enumerate(info_lines_final):
                        if output_start_y + 1 + idx >= main_area_h: break
                        stdscr.addstr(output_start_y + 1 + idx, 2, line)
                elif selected_col < len(task["steps"]):
                    step = task["steps"][selected_col]
                    header_name = model.dynamic_header[selected_col+2] if selected_col+2 < len(model.dynamic_header) else ""
                    stdscr.addstr(output_start_y, 1, f"Details for: {task['name']} -> {header_name}", curses.A_BOLD)
                    pid_str = f"PID: {step['process'].pid}" if step.get('process') and hasattr(step['process'], 'pid') and step['process'].pid else "PID: N/A"
                    stdscr.addstr(output_start_y, w - len(pid_str) - 1, pid_str)
                    
                    all_output_lines = read_log_files(step['log_path_stdout'], step['log_path_stderr'])
                    
                    max_scroll = max(0, len(all_output_lines) - (main_area_h - (output_start_y + 1)))
                    clamped_offset = min(log_scroll_offset, max_scroll)
                    if clamped_offset != log_scroll_offset: view_state['log_scroll_offset'] = clamped_offset
                    
                    lines_to_display = all_output_lines[clamped_offset:]
                    
                    output_content_y = output_start_y + 1
                    for idx, (line, color_key) in enumerate(lines_to_display):
                        draw_y = output_content_y + idx
                        if draw_y >= main_area_h: break
                        attr = curses.color_pair(color_key) | curses.A_BOLD if line.startswith('[') else curses.color_pair(color_key)
                        stdscr.addstr(draw_y, 2, line.rstrip()[:w-3], attr)
                    
                    if clamped_offset > 0: stdscr.addstr(output_start_y, w - 15, "[^ ... more]", curses.color_pair(COLOR_PAIR_PENDING))
                    if clamped_offset < max_scroll: stdscr.addstr(main_area_h - 1, w - 15, "[v ... more]", curses.color_pair(COLOR_PAIR_PENDING))

    if debug_panel_active:
        stdscr.hline(main_area_h, 0, curses.ACS_HLINE, w)
        with model.state_lock:
            if model.tasks and selected_row < len(model.tasks):
                task = model.tasks[selected_row]
                if selected_col >= 0 and selected_col < len(task["steps"]):
                    step = task["steps"][selected_col]
                    header = model.dynamic_header[selected_col+2] if selected_col+2 < len(model.dynamic_header) else ""
                    panel_title, log_snapshot = f"Debug Log for {task['name']} -> {header}", list(step["debug_log"])
                else:
                    panel_title, log_snapshot = f"Debug Log for {task['name']}", ["Info column has no debug log."]
            else: panel_title, log_snapshot = "Debug Log (No task selected)", []
        stdscr.attron(curses.A_BOLD); stdscr.addstr(main_area_h + 1, 1, panel_title); stdscr.attroff(curses.A_BOLD)
        
        visible_debug_lines = debug_panel_height - 2
        if visible_debug_lines > 0:
            max_debug_scroll = max(0, len(log_snapshot) - visible_debug_lines)
            clamped_debug_offset = min(debug_scroll_offset, max_debug_scroll)
            if clamped_debug_offset != debug_scroll_offset: view_state['debug_scroll_offset'] = clamped_debug_offset

            for i, log_entry in enumerate(log_snapshot[clamped_debug_offset : clamped_debug_offset + visible_debug_lines]):
                draw_y = main_area_h + 2 + i
                if draw_y < h:
                    stdscr.addstr(draw_y, 1, log_entry[:w-2])
            
            if clamped_debug_offset > 0:
                stdscr.addstr(main_area_h + 1, w - 15, "[^ ... more]", curses.color_pair(COLOR_PAIR_PENDING))
            if clamped_debug_offset < max_debug_scroll:
                stdscr.addstr(h - 1, w - 15, "[v ... more]", curses.color_pair(COLOR_PAIR_PENDING))

    stdscr.refresh()