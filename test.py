#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HPC Interactive Task Runner (Modular & Robust)

An interactive, terminal-based tool to run and monitor multi-step tasks defined in a CSV file.
Designed to be called as a function `run(csv_path)` from other Python modules.
This version is compatible with Python 3.6 and higher.

Key Features:
- Encapsulated in a `run(csv_path)` function for modular use.
- Guarantees only one worker thread per task at all times.
- Supports re-running a task from any selected step ('r' key).
- Supports killing an entire task row ('k' key) without deadlocking.
- Robustly kills all running processes on exit (via 'q' or Ctrl+C).
- Defines SUCCESS as: Exit Code is 0 AND STDERR is empty.
- Prevents UI freezes and race conditions using a `run_id` and `thread.join()` mechanism.
- Displays both STDOUT and STDERR for the selected step, with correct line wrapping.
- Features a toggleable, context-aware debug panel ('d' key) with detailed logging.
"""

import curses
import csv
import subprocess
import threading
import time
import os
import signal
import sys
from textwrap import wrap
from collections import deque

# --- Application State (managed by the `run` function) ---
tasks = []
dynamic_header = []
# ### DEADLOCK FIX ###
# Use a Re-entrant Lock (RLock) instead of a standard Lock.
# This allows a thread that already holds the lock to acquire it again without blocking.
# This is crucial because helper functions like kill_process_group are called from
# within other functions that already hold the lock.
# For example, kill_process_group may be called recursively or from multiple places
# (such as during cleanup or when rerunning tasks), so using RLock prevents deadlocks
# when the same thread needs to acquire the lock multiple times.
state_lock = threading.RLock()
selected_row, selected_col = 0, 0
app_running = True
debug_panel_visible = False

# --- Status & Color Definitions ---
STATUS_PENDING, STATUS_RUNNING, STATUS_SUCCESS, STATUS_FAILED, STATUS_SKIPPED, STATUS_KILLED = \
    "PENDING", "RUNNING", "SUCCESS", "FAILED", "SKIPPED", "KILLED"

(COLOR_PAIR_DEFAULT, COLOR_PAIR_HEADER, COLOR_PAIR_PENDING, COLOR_PAIR_RUNNING,
 COLOR_PAIR_SUCCESS, COLOR_PAIR_FAILED, COLOR_PAIR_SKIPPED, COLOR_PAIR_SELECTED,
 COLOR_PAIR_OUTPUT_HEADER, COLOR_PAIR_TABLE_HEADER, COLOR_PAIR_KILLED) = range(1, 12)

# --- Core Functions ---

def reset_global_state():
    """Resets all state variables, making the `run` function re-entrant."""
    global tasks, dynamic_header, selected_row, selected_col, app_running, debug_panel_visible
    tasks, dynamic_header = [], []
    selected_row, selected_col = 0, 0
    app_running, debug_panel_visible = True, False

def log_debug_unsafe(task_index, step_index, message):
    """(UNSAFE) Adds a timestamped message to a step's debug log. MUST be called while holding the `state_lock`."""
    if task_index < len(tasks) and step_index < len(tasks[task_index]["steps"]):
        step = tasks[task_index]["steps"][step_index]
        timestamp = time.strftime("%H:%M:%S")
        step["debug_log"].append(f"[{timestamp}] {message}")

def setup_colors():
    """Initializes all color pairs used by the curses UI."""
    curses.start_color(); curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_WHITE, -1); curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(3, curses.COLOR_YELLOW, -1); curses.init_pair(4, curses.COLOR_CYAN, -1)
    curses.init_pair(5, curses.COLOR_GREEN, -1); curses.init_pair(6, curses.COLOR_RED, -1)
    curses.init_pair(7, curses.COLOR_BLUE, -1); curses.init_pair(8, curses.COLOR_BLACK, curses.COLOR_GREEN)
    curses.init_pair(9, curses.COLOR_YELLOW, -1); curses.init_pair(10, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(11, curses.COLOR_MAGENTA, -1)

def get_status_color(status):
    """Returns the appropriate curses color pair for a given status string."""
    return curses.color_pair({"PENDING": 3, "RUNNING": 4, "SUCCESS": 5, "FAILED": 6,
                             "SKIPPED": 7, "KILLED": 11}.get(status, 1))

def parse_command_for_header(command):
    if not command: return ""
    return command.strip().split()[0].split('/')[-1]

def load_tasks_from_csv(filename):
    """Loads tasks from the CSV file before any threading or UI starts."""
    global tasks, dynamic_header
    print(f"Loading tasks from '{filename}'...")
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            all_rows = [row for row in reader if row and row[0].strip()]
            if not all_rows: raise StopIteration
            longest_row = max(all_rows, key=len)
            dynamic_header = ["TaskName"] + [parse_command_for_header(cmd) for cmd in longest_row[1:]]
            for row in all_rows:
                task_name = row[0]
                commands = [cmd for cmd in row[1:] if cmd.strip()]
                steps = [{"command": cmd, "status": "PENDING", "process": None,
                          "output": {"stdout": "", "stderr": "", "code": None},
                          "debug_log": deque(maxlen=50)} for cmd in commands]
                tasks.append({"name": task_name, "steps": steps, "thread": None, "run_id": 0})
        print("Tasks loaded successfully.")
    except Exception as e:
        print(f"FATAL: Error loading tasks from '{filename}': {e}"); sys.exit(1)

def kill_process_group(task_index, step_index, process):
    """Safely terminates a process and its entire process group."""
    if process and process.poll() is None:
        try:
            pgid = os.getpgid(process.pid)
            with state_lock: log_debug_unsafe(task_index, step_index, f"Killing process group {pgid}...")
            os.killpg(pgid, signal.SIGTERM); process.wait(timeout=2)
        except (ProcessLookupError, PermissionError):
            with state_lock: log_debug_unsafe(task_index, step_index, f"PGID for PID {process.pid} already gone.")
        except subprocess.TimeoutExpired:
            with state_lock: log_debug_unsafe(task_index, step_index, f"PG unresponsive, sending SIGKILL.")
            os.killpg(pgid, signal.SIGKILL)

def run_task_row(task_index, start_step_index, run_id):
    """Executes the steps for a given task sequentially. This is the main function for worker threads."""
    for i in range(start_step_index, len(tasks[task_index]["steps"])):
        step = tasks[task_index]["steps"][i]
        with state_lock:
            if tasks[task_index]['run_id'] != run_id: return
            if i > 0 and tasks[task_index]["steps"][i-1]["status"] in ["FAILED", "SKIPPED", "KILLED"]:
                step["status"] = "SKIPPED"; continue
            step["status"] = "RUNNING"
            log_debug_unsafe(task_index, i, f"Starting (run_id {run_id}).")
        try:
            popen_kwargs = {"shell": True, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE,
                            "preexec_fn": os.setsid, "encoding": 'utf-8'}
            if sys.version_info >= (3, 7): 
                popen_kwargs['text'] = True
                popen_kwargs['text'] = True
                process = subprocess.Popen(step["command"], **popen_kwargs)
                if tasks[task_index]['run_id'] != run_id: 
                    kill_process_group(task_index, i, process)
                    return
                step["process"] = process
                log_debug_unsafe(task_index, i, f"Process started with PID: {process.pid}")
            stdout, stderr = process.communicate()
            return_code = process.returncode
            with state_lock:
                if tasks[task_index]['run_id'] != run_id: return
                step["output"] = {"stdout": stdout, "stderr": stderr, "code": return_code}
                if step["status"] == "RUNNING":
                    if return_code == 0 and not stderr.strip(): step["status"] = "SUCCESS"
                    else: step["status"] = "FAILED"
                log_debug_unsafe(task_index, i, f"Process finished with code {return_code}. Status set to: {step['status']}.")
                if step["status"] != "SUCCESS":
                    for j in range(i + 1, len(tasks[task_index]["steps"])): tasks[task_index]["steps"][j]["status"] = "SKIPPED"
                    break
        except Exception as e:
            with state_lock:
                if tasks[task_index]['run_id'] != run_id: return
                step["status"] = "FAILED"; step["output"]["stderr"] = str(e); step["output"]["code"] = -1
                log_debug_unsafe(task_index, i, f"CRITICAL ERROR: {e}")
            break

def rerun_task_from_step(task_index, start_step_index):
    """Handles 'rerun' by safely terminating the old worker thread before starting a new one."""
    old_thread = None
    with state_lock:
        task = tasks[task_index]
        log_debug_unsafe(task_index, start_step_index, "RERUN triggered.")
        old_thread = task.get("thread")
        task['run_id'] += 1
        new_run_id = task['run_id']
        log_debug_unsafe(task_index, start_step_index, f"New run_id is {new_run_id}. Invalidating old thread.")
        for i in range(start_step_index, len(task["steps"])):
            if task["steps"][i]["process"]: kill_process_group(task_index, i, task["steps"][i]["process"])
            if task["steps"][i]["status"] == "RUNNING": task["steps"][i]["status"] = "KILLED"
        for i in range(start_step_index, len(task["steps"])):
            step = task["steps"][i]
            step["status"] = "PENDING"; step["output"] = {"stdout": "", "stderr": "", "code": None}
    if old_thread and old_thread.is_alive():
        with state_lock: log_debug_unsafe(task_index, start_step_index, f"Waiting for old thread {old_thread.ident} to join...")
        old_thread.join(timeout=2.0)
        with state_lock: log_debug_unsafe(task_index, start_step_index, "Old thread joined.")
    new_thread = threading.Thread(target=run_task_row, args=(task_index, start_step_index, new_run_id))
    new_thread.daemon = True
    with state_lock: tasks[task_index]["thread"] = new_thread; log_debug_unsafe(task_index, start_step_index, f"Starting new thread {new_thread.ident}...")
    new_thread.start()

def kill_task_row(task_index):
    """Terminates an entire task row and ensures its worker thread has exited."""
    old_thread = None
    with state_lock:
        task = tasks[task_index]
        log_debug_unsafe(task_index, selected_col, "KILL TASK triggered.")
        old_thread = task.get("thread")
        task['run_id'] += 1
        log_debug_unsafe(task_index, selected_col, f"New run_id is {task['run_id']} to halt execution.")
        kill_point_found = False
        for i, step in enumerate(task["steps"]):
            if step["status"] == "RUNNING":
                if step["process"]: kill_process_group(task_index, i, step["process"])
                step["status"] = "KILLED"
                kill_point_found = True
            elif step["status"] == "PENDING" and kill_point_found: step["status"] = "SKIPPED"
    if old_thread and old_thread.is_alive():
        with state_lock: log_debug_unsafe(task_index, selected_col, f"Waiting for killed thread {old_thread.ident} to join...")
        old_thread.join(timeout=2.0)
        with state_lock: log_debug_unsafe(task_index, selected_col, "Killed thread joined.")

def cleanup_all_processes():
    """Iterates through all tasks, kills their processes, and waits for their threads to exit."""
    threads_to_join = []
    with state_lock:
        for task_index, task in enumerate(tasks):
            task['run_id'] += 1
            if task.get("thread") and task["thread"].is_alive(): threads_to_join.append(task["thread"])
            for step_index, step in enumerate(task["steps"]):
                if step["process"]: kill_process_group(task_index, step_index, step["process"])
    for thread in threads_to_join: thread.join(timeout=1.0)

def draw_ui(stdscr):
    """Draws the entire terminal UI."""
    stdscr.erase(); h, w = stdscr.getmaxyx()
    debug_panel_height = 12 if debug_panel_visible else 0; main_area_h = h - debug_panel_height
    help_text = "ARROWS: Navigate | 'r': Rerun | 'k': Kill Task | 'd': Debug | 'q': Quit"
    stdscr.attron(curses.color_pair(2)); stdscr.addstr(0, 0, "HPC Interactive Task Runner".ljust(w)); stdscr.addstr(1, 0, help_text.ljust(w)); stdscr.attroff(curses.color_pair(2))
    with state_lock:
        max_name_len = max([len(t['name']) for t in tasks] + [len(dynamic_header[0])]) if tasks else 10
        col_width = max([len(h) for h in dynamic_header[1:]] + [12]) + 2 if dynamic_header and len(dynamic_header) > 1 else 12
        header_y, y = 3, 4
        stdscr.addstr(header_y, 1, dynamic_header[0].ljust(max_name_len), curses.A_BOLD)
        for j, col_name in enumerate(dynamic_header[1:]):
            start_x = max_name_len + 3 + (j * col_width)
            if start_x + col_width < w: stdscr.attron(curses.color_pair(10)); stdscr.addstr(header_y, start_x, col_name.center(col_width)); stdscr.attroff(curses.color_pair(10))
        for i, task in enumerate(tasks):
            if y >= main_area_h - 2: break
            stdscr.addstr(y, 1, task["name"].ljust(max_name_len), curses.A_REVERSE if i == selected_row else curses.A_NORMAL)
            for j, step in enumerate(task["steps"]):
                attr = curses.color_pair(8) if (i == selected_row and j == selected_col) else get_status_color(step["status"])
                start_x = max_name_len + 3 + (j * col_width)
                if start_x + col_width < w: stdscr.addstr(y, start_x, f" {step['status']} ".center(col_width), attr)
            y += 1
        output_start_y = y + 1
        if output_start_y < main_area_h - 1:
            stdscr.hline(output_start_y - 1, 0, curses.ACS_HLINE, w)
            if tasks and selected_row < len(tasks) and selected_col < len(tasks[selected_row]["steps"]):
                task, step = tasks[selected_row], tasks[selected_row]["steps"][selected_col]
                header_name = dynamic_header[selected_col+1] if selected_col+1 < len(dynamic_header) else ""
                stdscr.addstr(output_start_y, 1, f"Details for: {task['name']} -> {header_name}", curses.A_BOLD)
                pid_str = f"PID: {step['process'].pid}" if step['process'] and hasattr(step['process'], "pid") and step['process'].pid else "PID: N/A"; stdscr.addstr(output_start_y, w - len(pid_str) - 1, pid_str)
                stdscr.addstr(output_start_y + 1, 1, f"Command: {step['command']}")
                content_width = w - 4; stdout_header_y = output_start_y + 2
                stdscr.attron(curses.color_pair(9) | curses.A_BOLD); stdscr.addstr(stdout_header_y, 1, f"STDOUT (Exit Code: {step['output'].get('code', 'N/A')})"); stdscr.attroff(curses.color_pair(9) | curses.A_BOLD)
                out_lines = []; stdout_content_y = stdout_header_y + 1
                for line in step['output']['stdout'].strip().splitlines(): out_lines.extend(wrap(line, content_width, break_long_words=False, replace_whitespace=False) or [''])
                for idx, line in enumerate(out_lines):
                    if stdout_content_y + idx >= main_area_h - 1: break
                    stdscr.addstr(stdout_content_y + idx, 2, line)
                stderr_content = step['output']['stderr'].strip()
                if stderr_content:
                    stderr_header_y = stdout_content_y + len(out_lines) + (1 if out_lines else 0)
                    if stderr_header_y < main_area_h - 1:
                        stdscr.attron(curses.color_pair(6) | curses.A_BOLD); stdscr.addstr(stderr_header_y, 1, "STDERR"); stdscr.attroff(curses.color_pair(6) | curses.A_BOLD)
                        err_lines = []; stderr_content_y = stderr_header_y + 1
                        for line in stderr_content.splitlines(): err_lines.extend(wrap(line, content_width, break_long_words=False, replace_whitespace=False) or [''])
                        for idx, line in enumerate(err_lines):
                            if stderr_content_y + idx >= main_area_h - 1: break
                            stdscr.addstr(stderr_content_y + idx, 2, line, curses.color_pair(6))
    if debug_panel_visible:
        stdscr.hline(main_area_h - 1, 0, curses.ACS_HLINE, w)
        with state_lock:
            if tasks and selected_row < len(tasks) and selected_col < len(tasks[selected_row]["steps"]):
                step, task = tasks[selected_row]["steps"][selected_col], tasks[selected_row]
                header = dynamic_header[selected_col+1] if selected_col+1 < len(dynamic_header) else ""
                panel_title, log_snapshot = f"Debug Log for {task['name']} -> {header}", list(step["debug_log"])
            else: panel_title, log_snapshot = "Debug Log (No step selected)", []
        stdscr.attron(curses.A_BOLD); stdscr.addstr(main_area_h, 1, panel_title); stdscr.attroff(curses.A_BOLD)
        for i, log_entry in enumerate(log_snapshot[-(debug_panel_height-2):]):
            if main_area_h + 1 + i < h: stdscr.addstr(main_area_h + 1 + i, 1, log_entry[:w-2])
    stdscr.refresh()

def _main_curses_loop(stdscr, csv_path):
    """The internal main function called by curses.wrapper. Sets up and runs the event loop."""
    global selected_row, selected_col, app_running, debug_panel_visible
    curses.curs_set(0); stdscr.nodelay(1); setup_colors()
    load_tasks_from_csv(csv_path)
    for i in range(len(tasks)):
        thread = threading.Thread(target=run_task_row, args=(i, 0, tasks[i]['run_id']))
        thread.daemon = True;
        with state_lock: tasks[i]["thread"] = thread
        thread.start()
    while app_running:
        draw_ui(stdscr)
        try: key = stdscr.getch()
        except curses.error: key = -1
        if key != -1:
            if key == ord('d'): debug_panel_visible = not debug_panel_visible
            elif key == ord('q'):
                with state_lock: log_debug_unsafe(0,0,"'q' key pressed. Shutting down.")
                app_running = False
            else:
                rerun_triggered, kill_triggered = False, False
                with state_lock:
                    if key == curses.KEY_UP: selected_row = max(0, selected_row - 1)
                    elif key == curses.KEY_DOWN: selected_row = min(len(tasks) - 1, selected_row + 1)
                    elif key == curses.KEY_LEFT: selected_col = max(0, selected_col - 1)
                    elif key == curses.KEY_RIGHT:
                        if tasks and selected_row < len(tasks):
                            max_col = len(tasks[selected_row]["steps"]) - 1
                            selected_col = min(max_col, selected_col + 1)
                    elif key == ord('r'):
                        if tasks and selected_row < len(tasks) and selected_col < len(tasks[selected_row]["steps"]):
                             rerun_triggered = True; log_debug_unsafe(selected_row, selected_col, "'r' key pressed.")
                    elif key == ord('k'):
                        if tasks and selected_row < len(tasks):
                            kill_triggered = True; log_debug_unsafe(selected_row, selected_col, "'k' key pressed.")
                if rerun_triggered: rerun_task_from_step(selected_row, selected_col)
                if kill_triggered: kill_task_row(selected_row)
        time.sleep(0.05)
    stdscr.erase(); stdscr.attron(curses.A_BOLD); stdscr.addstr(0, 0, "Quitting: Cleaning up all running processes..."); stdscr.attroff(curses.A_BOLD); stdscr.refresh()
    cleanup_all_processes()
    time.sleep(1)

def run(csv_path: str):
    """
    Main entry point for running the task runner application.
    This function can be imported and called from other Python modules.
    """
    reset_global_state()
    try:
        curses.wrapper(_main_curses_loop, csv_path)
    except KeyboardInterrupt:
        print("\nInterrupted by user (Ctrl+C). Cleaning up...")
        cleanup_all_processes()
        print("Cleanup complete. Exiting.")
    except Exception:
        import traceback
        try:
            curses.nocbreak()
            curses.echo()
            curses.endwin()
        except Exception:
            pass
        print("\nAn unexpected error occurred. Please see the traceback below:")
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) > 1: csv_file = sys.argv[1]
    else:
        csv_file = 'tasks.csv'
        print(f"Usage: python {sys.argv[0]} [path/to/your.csv]"); print(f"No CSV file provided. Using default '{csv_file}'")
    if not os.path.exists(csv_file): print(f"Error: CSV file not found at '{csv_file}'"); sys.exit(1)
    if os.name != 'posix': print("This script requires a POSIX-like OS (Linux, macOS)."); time.sleep(3); exit(1)
    run(csv_path=csv_file)