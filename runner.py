#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TaskPanel - Controller (Production-Ready with Smart Refresh)
"""
import curses
import os
import sys
import time
import argparse
from concurrent.futures import ThreadPoolExecutor

from model import TaskModel, STATUS_FAILED, STATUS_RUNNING, STATUS_PENDING, STATUS_SUCCESS
from view import setup_colors, draw_ui, calculate_layout_dimensions

class AppController:
    """Manages the application's main loop, user input, and state transitions."""
    def __init__(self, stdscr, csv_path: str, max_workers: int):
        self.stdscr = stdscr
        self.model = TaskModel(csv_path)
        self.app_running = True
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.view_state = {
            'top_row': 0, 
            'selected_row': 0, 
            'selected_col': 0, 
            'debug_panel_visible': False, 
            'left_most_step': 0, 
            'log_scroll_offset': 0,
            'debug_scroll_offset': 0 
        }
        self.ui_dirty = True
        curses.curs_set(0); stdscr.nodelay(1); setup_colors()
        self.model.load_tasks_from_csv()

    def start_initial_tasks(self):
        """Submits tasks that need to be run to the thread pool."""
        print(f"Submitting tasks to a pool of {self.executor._max_workers} worker(s)...")
        for i in range(len(self.model.tasks)):
            with self.model.state_lock:
                task = self.model.tasks[i]
                first_step_to_run = -1
                for j, step in enumerate(task['steps']):
                    if step['status'] != STATUS_SUCCESS:
                        first_step_to_run = j
                        break
                if first_step_to_run != -1:
                    task['run_counter'] += 1
                    current_run_counter = task['run_counter']
                    self.executor.submit(self.model.run_task_row, i, current_run_counter, first_step_to_run)
    
    def _reset_scroll_states(self):
        """Helper to reset all scroll offsets when selection changes."""
        self.view_state['log_scroll_offset'] = 0
        self.view_state['debug_scroll_offset'] = 0

    def handle_input(self):
        """Processes a single key press, including enhanced navigation."""
        try: key = self.stdscr.getch()
        except curses.error: key = -1

        if key == curses.KEY_RESIZE:
            self.ui_dirty = True
            return

        if key == -1: return
        
        self.ui_dirty = True
        vs = self.view_state
        h, w = self.stdscr.getmaxyx()
        
        _, _, _, _, task_list_h = \
            calculate_layout_dimensions(w, self.model, h, vs['debug_panel_visible'])
        
        # Navigation and Action keys
        if key == ord('d'): vs['debug_panel_visible'] = not vs['debug_panel_visible']
        elif key == ord('q'): self.app_running = False
        elif key == curses.KEY_UP: 
            vs['selected_row'] = max(0, vs['selected_row'] - 1)
            vs['top_row'] = min(vs['top_row'], vs['selected_row'])
            self._reset_scroll_states()
        elif key == curses.KEY_DOWN: 
            vs['selected_row'] = min(len(self.model.tasks) - 1, vs['selected_row'] + 1)
            vs['top_row'] = max(vs['top_row'], vs['selected_row'] - task_list_h + 1)
            self._reset_scroll_states()
        elif key == curses.KEY_HOME: 
            vs['selected_row'], vs['top_row'] = 0, 0
            self._reset_scroll_states()
        elif key == curses.KEY_END: 
            vs['selected_row'] = len(self.model.tasks) - 1
            vs['top_row'] = max(0, vs['selected_row'] - task_list_h + 1)
            self._reset_scroll_states()
        elif key == curses.KEY_PPAGE: 
            vs['selected_row'] = max(0, vs['selected_row'] - task_list_h)
            vs['top_row'] = max(0, vs['top_row'] - task_list_h)
            self._reset_scroll_states()
        elif key == curses.KEY_NPAGE: 
            vs['selected_row'] = min(len(self.model.tasks) - 1, vs['selected_row'] + task_list_h)
            vs['top_row'] = min(max(0, len(self.model.tasks) - task_list_h), vs['top_row'] + task_list_h)
            self._reset_scroll_states()
        elif key == curses.KEY_LEFT:
            vs['selected_col'] = max(-1, vs['selected_col'] - 1)
            if vs['selected_col'] < vs['left_most_step']: vs['left_most_step'] = max(0, vs['selected_col'])
            self._reset_scroll_states()
        elif key == curses.KEY_RIGHT:
            with self.model.state_lock:
                if self.model.tasks and vs['selected_row'] < len(self.model.tasks):
                    steps = self.model.tasks[vs['selected_row']]["steps"]
                    if steps:
                        max_col = len(steps) - 1
                        vs['selected_col'] = min(max_col, vs['selected_col'] + 1)
                        max_name_len = max([len(t['name']) for t in self.model.tasks] + [len(self.model.dynamic_header[0])])
                        info_col_width = 20
                        step_col_width = max([len(h) for h in self.model.dynamic_header[2:]] + [12]) + 2 if len(self.model.dynamic_header) > 2 else 12
                        
                        steps_start_x = 1 + max_name_len + 2 + info_col_width + 3
                        available_width = w - steps_start_x
                        num_visible_steps = max(1, available_width // step_col_width)
                        
                        if vs['selected_col'] >= vs['left_most_step'] + num_visible_steps:
                            vs['left_most_step'] = vs['selected_col'] - num_visible_steps + 1
            self._reset_scroll_states()
        
        # Log Panel Scrolling
        elif key == ord('['): vs['log_scroll_offset'] = max(0, vs['log_scroll_offset'] - 1)
        elif key == ord(']'): vs['log_scroll_offset'] += 1

        # Debug Panel Scrolling
        elif key == ord('{'): vs['debug_scroll_offset'] = max(0, vs['debug_scroll_offset'] - 1)
        elif key == ord('}'): vs['debug_scroll_offset'] += 1

        # Task Actions
        elif key == ord('r'):
            if vs['selected_col'] >= 0:
                with self.model.state_lock:
                    if self.model.tasks and vs['selected_row'] < len(self.model.tasks) and vs['selected_col'] < len(self.model.tasks[vs['selected_row']]["steps"]):
                        
                        # ### NEW: Pre-rerun validation logic. ###
                        # Before rerunning a step, we must ensure all preceding steps in the
                        # same task have the status SUCCESS. This enforces strict sequential dependency.
                        task = self.model.tasks[vs['selected_row']]
                        step_to_rerun_idx = vs['selected_col']
                        is_rerun_allowed = True
                        
                        for i in range(step_to_rerun_idx):
                            if task["steps"][i]["status"] != STATUS_SUCCESS:
                                is_rerun_allowed = False
                                break
                        
                        if is_rerun_allowed:
                            self.model._log_debug_unsafe(vs['selected_row'], step_to_rerun_idx, "'r' key pressed by user. Rerun allowed.")
                            self.model.rerun_task_from_step(self.executor, vs['selected_row'], step_to_rerun_idx)
                        else:
                            # If not allowed, flash the screen to give feedback and log the reason.
                            curses.flash()
                            self.model._log_debug_unsafe(vs['selected_row'], step_to_rerun_idx, "Rerun blocked: A preceding step has not completed successfully.")

        elif key == ord('k'):
            if self.model.tasks and vs['selected_row'] < len(self.model.tasks):
                with self.model.state_lock:
                    if self.model.tasks[vs['selected_row']]['steps']:
                        self.model._log_debug_unsafe(vs['selected_row'], 0, "'k' key pressed for this task.")
                    self.model.kill_task_row(vs['selected_row'])

    def run_loop(self):
        """The main event loop of the application."""
        self.start_initial_tasks()
        last_state_snapshot = None
        while self.app_running:
            with self.model.state_lock:
                current_state_snapshot = [s['status'] for t in self.model.tasks for s in t['steps']]
            if current_state_snapshot != last_state_snapshot:
                self.ui_dirty = True
                last_state_snapshot = current_state_snapshot
            if self.ui_dirty:
                draw_ui(self.stdscr, self.model, self.view_state)
                self.ui_dirty = False
            self.handle_input()
            time.sleep(0.05)
        
        if sys.version_info >= (3, 9): self.executor.shutdown(wait=False, cancel_futures=True)
        else: self.executor.shutdown(wait=False)
        self.stdscr.erase(); self.stdscr.attron(curses.A_BOLD); self.stdscr.addstr(0, 0, "Quitting: Cleaning up and saving state..."); self.stdscr.attroff(curses.A_BOLD); self.stdscr.refresh()
        self.model.cleanup()
        time.sleep(1)

def run(csv_path: str, max_workers: int):
    """Main entry point for running the TaskPanel application."""
    app_controller = None
    try:
        def main_wrapper(stdscr):
            nonlocal app_controller
            app_controller = AppController(stdscr, csv_path, max_workers)
            app_controller.run_loop()
        curses.wrapper(main_wrapper)
    except KeyboardInterrupt:
        print("\nInterrupted by user (Ctrl+C). Saving state and exiting.")
        if app_controller:
            app_controller.model.cleanup()
        else: 
            TaskModel(csv_path).persist_state()
        print("Cleanup complete.")
    except Exception:
        import traceback
        try: curses.nocbreak(); curses.echo(); curses.endwin()
        except: pass
        print("\nAn unexpected error occurred:")
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TaskPanel: A robust, interactive, terminal-based tool to run and monitor multi-step tasks.")
    parser.add_argument("csv_path", nargs='?', default="tasks.csv", help="Path to the tasks CSV file (default: tasks.csv)")
    parser.add_argument("-w", "--max-workers", type=int, default=os.cpu_count() or 4, help=f"Maximum number of parallel tasks to run (default: number of CPU cores, currently {os.cpu_count() or 4})")
    args = parser.parse_args()
    if not os.path.exists(args.csv_path): print(f"Error: CSV file not found at '{args.csv_path}'"); sys.exit(1)
    if os.name != 'posix': print("This script requires a POSIX-like OS (Linux, macOS)."); time.sleep(3); exit(1)
    run(csv_path=args.csv_path, max_workers=args.max_workers)