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
    
    # ### MODIFIED: Re-added dynamic layout for debug panel ###
    MIN_MAIN_HEIGHT = 10; FIXED_DEBUG_HEIGHT = 12
    debug_panel_requested = view_state['debug_panel_visible']; debug_panel_active = debug_panel_requested; warning_message = ""
    if debug_panel_requested and h < MIN_MAIN_HEIGHT + FIXED_DEBUG_HEIGHT:
        debug_panel_active = False; warning_message = " (Debug hidden: terminal too small)"
    debug_panel_height = FIXED_DEBUG_HEIGHT if debug_panel_active else 0
    main_area_h = h - debug_panel_height

    # ### MODIFIED: Updated help text ###
    help_text = "ARROWS/PgUp/PgDn/Home/End: Nav | r: Rerun | k: Kill | d: Debug | q: Quit"
    help_text += warning_message
    stdscr.attron(curses.color_pair(COLOR_PAIR_HEADER)); stdscr.addstr(0, 0, "HPC Interactive Task Runner".ljust(w)); stdscr.addstr(1, 0, help_text.ljust(w)); stdscr.attroff(curses.color_pair(COLOR_PAIR_HEADER))
    
    with model.state_lock:
        if not model.tasks:
            if main_area_h > 3: stdscr.addstr(3, 1, "No tasks loaded.")
            stdscr.refresh(); return
        
        max_name_len = max([len(t['name']) for t in model.tasks] + [len(model.dynamic_header[0])])
        info_col_width = 20 # Fixed width for the Info column
        step_col_width = max([len(h) for h in model.dynamic_header[2:]] + [12]) + 2 if len(model.dynamic_header) > 2 else 12
        
        header_y, y_start = 3, 4
        
        if header_y < main_area_h:
            stdscr.addstr(header_y, 1, model.dynamic_header[0].ljust(max_name_len), curses.A_BOLD)
            
            info_header_x = 1 + max_name_len + 2
            stdscr.attron(curses.color_pair(COLOR_PAIR_TABLE_HEADER))
            stdscr.addstr(header_y, info_header_x, model.dynamic_header[1].center(info_col_width))
            stdscr.attroff(curses.color_pair(COLOR_PAIR_TABLE_HEADER))

            # Draw Step Headers
            for j, col_name in enumerate(model.dynamic_header[2:]):
                start_x = info_header_x + info_col_width + 3 + (j * step_col_width)
                if start_x + step_col_width < w:
                    stdscr.attron(curses.color_pair(COLOR_PAIR_TABLE_HEADER))
                    stdscr.addstr(header_y, start_x, col_name.center(step_col_width))
                    stdscr.attroff(curses.color_pair(COLOR_PAIR_TABLE_HEADER))

        task_list_h = main_area_h - y_start - 3
        last_drawn_y = y_start - 1
        
        for i in range(view_state['top_row'], min(view_state['top_row'] + task_list_h, len(model.tasks))):
            draw_y = y_start + (i - view_state['top_row'])
            if draw_y >= main_area_h: break
            task = model.tasks[i]
            # Draw TaskName
            stdscr.addstr(draw_y, 1, task["name"].ljust(max_name_len), curses.A_REVERSE if i == view_state['selected_row'] else curses.A_NORMAL)
            # Draw Info
            info_text_x = 1 + max_name_len + 2
            info_text = task.get('info', '')
            stdscr.addstr(draw_y, info_text_x, info_text[:info_col_width-1].center(info_col_width))

            for j, step in enumerate(task["steps"]):
                attr = curses.color_pair(COLOR_PAIR_SELECTED) if (i == view_state['selected_row'] and j == view_state['selected_col']) else get_status_color(step["status"])
                start_x = info_text_x + info_col_width + 3 + (j * step_col_width)
                if start_x + step_col_width < w: stdscr.addstr(draw_y, start_x, f" {step['status']} ".center(step_col_width), attr)
            last_drawn_y = draw_y
            
        output_start_y = last_drawn_y + 2
        if output_start_y < main_area_h:
            stdscr.hline(output_start_y - 1, 0, curses.ACS_HLINE, w)
            if model.tasks and view_state['selected_row'] < len(model.tasks) and view_state['selected_col'] < len(model.tasks[view_state['selected_row']]["steps"]):
                task, step = model.tasks[view_state['selected_row']], model.tasks[view_state['selected_row']]["steps"][view_state['selected_col']]
                header_name = model.dynamic_header[view_state['selected_col']+1] if view_state['selected_col']+1 < len(model.dynamic_header) else ""
                
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
                header = model.dynamic_header[view_state['selected_col']+1] if view_state['selected_col']+1 < len(model.dynamic_header) else ""
                panel_title, log_snapshot = f"Debug Log for {task['name']} -> {header}", list(step["debug_log"])
            else: panel_title, log_snapshot = "Debug Log (No step selected)", []
        stdscr.attron(curses.A_BOLD); stdscr.addstr(main_area_h + 1, 1, panel_title); stdscr.attroff(curses.A_BOLD)
        for i, log_entry in enumerate(log_snapshot[-(debug_panel_height-2):]):
            if main_area_h + 2 + i < h: stdscr.addstr(main_area_h + 2 + i, 1, log_entry[:w-2])

    stdscr.refresh()