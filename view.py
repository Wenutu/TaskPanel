#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HPC Task Runner - View (Refined with Debug Panel)
"""
import curses
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

def draw_ui(stdscr, model, view_state):
    stdscr.erase(); h, w = stdscr.getmaxyx()
    if h < 8: stdscr.addstr(0, 0, "Terminal too small."); stdscr.refresh(); return
    
    top_row, selected_row, selected_col = view_state['top_row'], view_state['selected_row'], view_state['selected_col']
    left_most_step = view_state['left_most_step']
    debug_panel_visible = view_state['debug_panel_visible']
    MIN_MAIN_HEIGHT = 10; FIXED_DEBUG_HEIGHT = 12
    debug_panel_active = debug_panel_visible; warning_message = ""
    if debug_panel_visible and h < MIN_MAIN_HEIGHT + FIXED_DEBUG_HEIGHT:
        debug_panel_active = False; warning_message = " (Debug hidden: terminal too small)"
    debug_panel_height = FIXED_DEBUG_HEIGHT if debug_panel_active else 0
    main_area_h = h - debug_panel_height

    help_text = "ARROWS/PgUp/PgDn/Home/End: Nav | r: Rerun | k: Kill | d: Debug | q: Quit"
    help_text += warning_message
    stdscr.attron(curses.color_pair(COLOR_PAIR_HEADER)); stdscr.addstr(0, 0, "HPC Interactive Task Runner".ljust(w)); stdscr.addstr(1, 0, help_text.ljust(w)); stdscr.attroff(curses.color_pair(COLOR_PAIR_HEADER))
    
    with model.state_lock:
        if not model.tasks:
            if h > 3: stdscr.addstr(3, 1, "No tasks loaded.")
            stdscr.refresh(); return
        
        max_name_len = max([len(t['name']) for t in model.tasks] + [len(model.dynamic_header[0])]) + 2
        info_col_width = 20
        step_col_width = max([len(h) for h in model.dynamic_header[2:]] + [12]) + 2 if len(model.dynamic_header) > 2 else 12
        
        header_y, y_start = 3, 4
        
        if header_y < main_area_h:
            stdscr.attron(curses.color_pair(COLOR_PAIR_TABLE_HEADER))
            stdscr.addstr(header_y, 1, model.dynamic_header[0].center(max_name_len))
            stdscr.attroff(curses.color_pair(COLOR_PAIR_TABLE_HEADER))
            info_header_x = 1 + max_name_len + 2
            stdscr.attron(curses.color_pair(COLOR_PAIR_TABLE_HEADER)); stdscr.addstr(header_y, info_header_x, model.dynamic_header[1].center(info_col_width)); stdscr.attroff(curses.color_pair(COLOR_PAIR_TABLE_HEADER))
            
            # Draw headers based on horizontal scroll
            available_width = w - (info_header_x + info_col_width + 3)
            num_visible_steps = max(1, available_width // step_col_width)
            for i in range(left_most_step, min(left_most_step + num_visible_steps, len(model.dynamic_header) - 2)):
                j = i - left_most_step # On-screen column index
                col_name = model.dynamic_header[i + 2]
                start_x = info_header_x + info_col_width + 3 + (j * step_col_width)
                if start_x + step_col_width < w: stdscr.attron(curses.color_pair(COLOR_PAIR_TABLE_HEADER)); stdscr.addstr(header_y, start_x, col_name.center(step_col_width)); stdscr.attroff(curses.color_pair(COLOR_PAIR_TABLE_HEADER))
        
        task_list_h = main_area_h - y_start - 3
        last_drawn_y = y_start - 1
        
        for i in range(top_row, min(top_row + task_list_h, len(model.tasks))):
            draw_y = y_start + (i - top_row)
            if draw_y >= main_area_h: break
            task = model.tasks[i]
            
            stdscr.addstr(draw_y, 1, task["name"].center(max_name_len), curses.A_REVERSE if i == selected_row else curses.A_NORMAL)
            
            # Highlight Info column if selected_col is -1
            info_text_x = 1 + max_name_len + 2
            full_info_text = task.get('info', '')
            # NEW: Split info into lines and take the first one
            info_lines = full_info_text.splitlines()
            first_line = info_lines[0] if info_lines else ""
            # Replace newline characters to avoid breaking the layout, just in case
            first_line = first_line.replace('\n', ' ').replace('\r', '')

            info_attr = curses.color_pair(COLOR_PAIR_SELECTED) if (i == selected_row and selected_col == -1) else curses.A_NORMAL
            stdscr.addstr(draw_y, info_text_x, first_line[:info_col_width-1].ljust(info_col_width), info_attr)
            
            # Draw step statuses based on horizontal scroll
            for j in range(left_most_step, min(left_most_step + num_visible_steps, len(task["steps"]))):
                on_screen_col_idx = j - left_most_step
                step = task["steps"][j]
                attr = curses.color_pair(COLOR_PAIR_SELECTED) if (i == selected_row and j == selected_col) else get_status_color(step["status"])
                start_x = info_text_x + info_col_width + 3 + (on_screen_col_idx * step_col_width)
                if start_x + step_col_width < w: stdscr.addstr(draw_y, start_x, f" {step['status']} ".center(step_col_width), attr)
            last_drawn_y = draw_y
            
        # --- Draw Output Panel with Context
        output_start_y = last_drawn_y + 2
        if output_start_y < main_area_h:
            stdscr.hline(output_start_y - 1, 0, curses.ACS_HLINE, w)                
            if model.tasks and selected_row < len(model.tasks):
                task = model.tasks[selected_row]
                if selected_col == -1:
                    stdscr.addstr(output_start_y, 1, f"Full Info for: {task['name']}", curses.A_BOLD)
                    info_lines = wrap(task.get('info', ''), w - 4) # This was the bug
                    for idx, line in enumerate(info_lines):
                        if output_start_y + 1 + idx >= main_area_h: break
                        stdscr.addstr(output_start_y + 1 + idx, 2, line)

                elif selected_col < len(task["steps"]): # A step column is selected
                    step = task["steps"][selected_col]
                    header_name = model.dynamic_header[selected_col+2] if selected_col+2 < len(model.dynamic_header) else ""
                    stdscr.addstr(output_start_y, 1, f"Details for: {task['name']} -> {header_name}", curses.A_BOLD)
                    pid_str = f"PID: {step['process'].pid}" if step.get('process') and hasattr(step['process'], 'pid') and step['process'].pid else "PID: N/A"
                    stdscr.addstr(output_start_y, w - len(pid_str) - 1, pid_str)
                    
                    output = step.get('output', {}); stdout_content = output.get('stdout', '').strip(); stderr_content = output.get('stderr', '').strip()
                    all_output_lines = []
                    if stdout_content:
                        all_output_lines.append(("[STDOUT]", COLOR_PAIR_OUTPUT_HEADER))
                        for line in stdout_content.splitlines(): all_output_lines.append((line, COLOR_PAIR_DEFAULT))
                    if stderr_content:
                        all_output_lines.append(("[STDERR]", COLOR_PAIR_FAILED))
                        for line in stderr_content.splitlines(): all_output_lines.append((line, COLOR_PAIR_STDERR))
                    
                    output_content_y = output_start_y + 1
                    for idx, (line, color_key) in enumerate(all_output_lines):
                        if output_content_y + idx >= main_area_h: break
                        attr = curses.color_pair(color_key) | curses.A_BOLD if line.startswith('[') else curses.color_pair(color_key)
                        stdscr.addstr(output_content_y + idx, 2, line[:w-3], attr)

    if debug_panel_active:
        stdscr.hline(main_area_h, 0, curses.ACS_HLINE, w)
        with model.state_lock:
            if model.tasks and view_state['selected_row'] < len(model.tasks) and view_state['selected_col'] < len(model.tasks[view_state['selected_row']]["steps"]):
                step, task = model.tasks[view_state['selected_row']]["steps"][view_state['selected_col']], model.tasks[view_state['selected_row']]
                header = model.dynamic_header[view_state['selected_col']+2] if view_state['selected_col']+2 < len(model.dynamic_header) else ""
                panel_title, log_snapshot = f"Debug Log for {task['name']} -> {header}", list(step["debug_log"])
            else: panel_title, log_snapshot = "Debug Log (No step selected)", []
        stdscr.attron(curses.A_BOLD); stdscr.addstr(main_area_h + 1, 1, panel_title); stdscr.attroff(curses.A_BOLD)
        for i, log_entry in enumerate(log_snapshot[-(debug_panel_height-2):]):
            if main_area_h + 2 + i < h: stdscr.addstr(main_area_h + 2 + i, 1, log_entry[:w-2])

    stdscr.refresh()