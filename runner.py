#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TaskPanel - Controller (Refactored for Clarity)

Acts as the Controller in the MVC pattern. It initializes the Model and View, handles
user input via a clean dispatch dictionary, manages the main application loop,
and schedules task execution using a thread pool.

Key Improvements:
- Uses a `dataclass` for `ViewState` to structure UI state.
- Refactors the monolithic `handle_input` into a dispatch dictionary (`key_handlers`)
  and smaller, single-purpose methods, making the code much easier to read and extend.
"""
import argparse
import curses
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from model import TaskModel, Status, TaskLoadError
from view import setup_colors, draw_ui, calculate_layout_dimensions, ViewState

class AppController:
    """Manages the application's main loop, user input, and state transitions."""
    def __init__(self, stdscr, csv_path: str, max_workers: int):
        self.stdscr = stdscr
        self.max_workers = max_workers
        self.model = TaskModel(csv_path)
        self.view_state = ViewState()
        self.app_running = True
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.ui_dirty = True  # Flag to trigger a redraw

        curses.curs_set(0)
        self.stdscr.nodelay(1)
        setup_colors()
        self.model.load_tasks_from_csv()

        # Input handling is simplified using a dispatch dictionary.
        self.key_handlers = {
            ord('q'): self._handle_quit,
            ord('d'): self._handle_toggle_debug,
            curses.KEY_UP: self._handle_nav_up,
            curses.KEY_DOWN: self._handle_nav_down,
            curses.KEY_LEFT: self._handle_nav_left,
            curses.KEY_RIGHT: self._handle_nav_right,
            curses.KEY_HOME: self._handle_nav_home,
            curses.KEY_END: self._handle_nav_end,
            curses.KEY_PPAGE: self._handle_nav_page_up,
            curses.KEY_NPAGE: self._handle_nav_page_down,
            ord('r'): self._handle_rerun,
            ord('k'): self._handle_kill,
            ord('['): self._handle_scroll_log_up,
            ord(']'): self._handle_scroll_log_down,
            ord('{'): self._handle_scroll_debug_up,
            ord('}'): self._handle_scroll_debug_down,
        }

    def start_initial_tasks(self):
        """Submits tasks that are not fully completed to the thread pool."""
        print(f"Submitting tasks to a pool of {self.max_workers} worker(s)...")
        for i, task in enumerate(self.model.tasks):
            with self.model.state_lock:
                first_step_to_run = -1
                # Find the first step that hasn't successfully completed.
                for j, step in enumerate(task.steps):
                    if step.status != Status.SUCCESS:
                        first_step_to_run = j
                        break

                if first_step_to_run != -1:
                    task.run_counter += 1
                    self.executor.submit(self.model.run_task_row, i, task.run_counter, first_step_to_run)

    def _reset_scroll_states(self):
        """Helper to reset all scroll offsets when selection changes."""
        self.view_state.log_scroll_offset = 0
        self.view_state.debug_scroll_offset = 0

    # --- Input Handler Methods (Refactored from single function) ---

    def _handle_quit(self): self.app_running = False
    def _handle_toggle_debug(self): self.view_state.debug_panel_visible = not self.view_state.debug_panel_visible
    def _handle_scroll_log_up(self): self.view_state.log_scroll_offset = max(0, self.view_state.log_scroll_offset - 1)
    def _handle_scroll_log_down(self): self.view_state.log_scroll_offset += 1
    def _handle_scroll_debug_up(self): self.view_state.debug_scroll_offset = max(0, self.view_state.debug_scroll_offset - 1)
    def _handle_scroll_debug_down(self): self.view_state.debug_scroll_offset += 1

    def _handle_nav_up(self):
        self.view_state.selected_row = max(0, self.view_state.selected_row - 1)
        self.view_state.top_row = min(self.view_state.top_row, self.view_state.selected_row)
        self._reset_scroll_states()

    def _handle_nav_down(self):
        h, w = self.stdscr.getmaxyx()
        layout = calculate_layout_dimensions(w, self.model, h, self.view_state.debug_panel_visible)
        self.view_state.selected_row = min(len(self.model.tasks) - 1, self.view_state.selected_row + 1)
        self.view_state.top_row = max(self.view_state.top_row, self.view_state.selected_row - layout['task_list_h'] + 1)
        self._reset_scroll_states()
    
    def _handle_nav_left(self):
        self.view_state.selected_col = max(-1, self.view_state.selected_col - 1)
        self.view_state.left_most_step = min(self.view_state.left_most_step, max(0, self.view_state.selected_col))
        self._reset_scroll_states()

    def _handle_nav_right(self):
        with self.model.state_lock:
            if not self.model.tasks or self.view_state.selected_row >= len(self.model.tasks): return
            task = self.model.tasks[self.view_state.selected_row]
            if not task.steps: return

            h, w = self.stdscr.getmaxyx()
            layout = calculate_layout_dimensions(w, self.model, h, self.view_state.debug_panel_visible)
            max_col = len(task.steps) - 1
            self.view_state.selected_col = min(max_col, self.view_state.selected_col + 1)
            
            if self.view_state.selected_col >= self.view_state.left_most_step + layout['num_visible_steps']:
                self.view_state.left_most_step = self.view_state.selected_col - layout['num_visible_steps'] + 1
        self._reset_scroll_states()
        
    def _handle_nav_home(self):
        self.view_state.selected_row, self.view_state.top_row = 0, 0
        self._reset_scroll_states()

    def _handle_nav_end(self):
        h, w = self.stdscr.getmaxyx()
        layout = calculate_layout_dimensions(w, self.model, h, self.view_state.debug_panel_visible)
        self.view_state.selected_row = len(self.model.tasks) - 1
        self.view_state.top_row = max(0, self.view_state.selected_row - layout['task_list_h'] + 1)
        self._reset_scroll_states()
    
    def _handle_nav_page_up(self):
        h, w = self.stdscr.getmaxyx()
        layout = calculate_layout_dimensions(w, self.model, h, self.view_state.debug_panel_visible)
        self.view_state.selected_row = max(0, self.view_state.selected_row - layout['task_list_h'])
        self.view_state.top_row = max(0, self.view_state.top_row - layout['task_list_h'])
        self._reset_scroll_states()

    def _handle_nav_page_down(self):
        h, w = self.stdscr.getmaxyx()
        layout = calculate_layout_dimensions(w, self.model, h, self.view_state.debug_panel_visible)
        num_tasks = len(self.model.tasks)
        self.view_state.selected_row = min(num_tasks - 1, self.view_state.selected_row + layout['task_list_h'])
        self.view_state.top_row = min(max(0, num_tasks - layout['task_list_h']), self.view_state.top_row + layout['task_list_h'])
        self._reset_scroll_states()

    def _handle_rerun(self):
        vs = self.view_state
        if vs.selected_col >= 0:
            with self.model.state_lock:
                task = self.model.tasks[vs.selected_row]
                if vs.selected_col < len(task.steps):
                    # Enforce strict sequential dependency: all preceding steps must be SUCCESS.
                    is_rerun_allowed = all(task.steps[i].status == Status.SUCCESS for i in range(vs.selected_col))
                    if is_rerun_allowed:
                        self.model._log_debug_unsafe(vs.selected_row, vs.selected_col, "'r' key pressed. Rerun allowed.")
                        self.model.rerun_task_from_step(self.executor, vs.selected_row, vs.selected_col)
                    else:
                        curses.flash() # Visual feedback for blocked action
                        self.model._log_debug_unsafe(vs.selected_row, vs.selected_col, "Rerun blocked: Preceding step not SUCCESS.")

    def _handle_kill(self):
        vs = self.view_state
        if self.model.tasks and vs.selected_row < len(self.model.tasks):
            with self.model.state_lock:
                if self.model.tasks[vs.selected_row].steps:
                    self.model._log_debug_unsafe(vs.selected_row, 0, "'k' key pressed for this task.")
                self.model.kill_task_row(vs.selected_row)
    
    def process_input(self):
        """Processes a single key press using the key handler dispatch dictionary."""
        try:
            key = self.stdscr.getch()
        except curses.error:
            key = -1
        
        if key in self.key_handlers:
            self.ui_dirty = True
            self.key_handlers[key]()

    def run_loop(self):
        """The main event loop of the application."""
        self.start_initial_tasks()
        last_state_snapshot = None
        while self.app_running:
            with self.model.state_lock:
                # Create a simple, comparable snapshot of the system's state.
                current_state_snapshot = [s.status.value for t in self.model.tasks for s in t.steps]

            # The UI is "dirty" and needs a redraw if the model's state has changed
            # or if user input has occurred (handled in `process_input`).
            if current_state_snapshot != last_state_snapshot:
                self.ui_dirty = True
                last_state_snapshot = current_state_snapshot

            if self.ui_dirty:
                draw_ui(self.stdscr, self.model, self.view_state)
                self.ui_dirty = False

            self.process_input()
            time.sleep(0.05) # Prevent high CPU usage.

        # --- Graceful Shutdown ---
        # The `cancel_futures` argument is available in Python 3.9+ and is more robust.
        if sys.version_info >= (3, 9): self.executor.shutdown(wait=False, cancel_futures=True)
        else: self.executor.shutdown(wait=False)
        
        self.stdscr.erase()
        self.stdscr.addstr(0, 0, "Quitting: Cleaning up and saving state...", curses.A_BOLD)
        self.stdscr.refresh()
        self.model.cleanup()
        time.sleep(1) # Allow user to see the message.

def run(csv_path: str, max_workers: int):
    """Main entry point for running the TaskPanel application."""
    app_controller = None
    try:
        def main_wrapper(stdscr):
            nonlocal app_controller
            app_controller = AppController(stdscr, csv_path, max_workers)
            app_controller.run_loop()
        curses.wrapper(main_wrapper)
    except TaskLoadError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user (Ctrl+C). Saving state and exiting.")
        if app_controller: app_controller.model.cleanup()
    except Exception:
        # On any unexpected crash, ensure the terminal is restored to a usable state.
        try: curses.nocbreak(); curses.echo(); curses.endwin()
        except: pass
        import traceback
        print("\nAn unexpected error occurred:", file=sys.stderr)
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TaskPanel: A robust, terminal-based tool to run and monitor multi-step tasks.")
    parser.add_argument("csv_path", nargs='?', default="tasks.csv", help="Path to the tasks CSV file (default: tasks.csv)")
    parser.add_argument("-w", "--max-workers", type=int, default=os.cpu_count() or 4, help=f"Max parallel tasks (default: CPU cores, currently {os.cpu_count() or 4})")
    args = parser.parse_args()
    if not os.path.exists(args.csv_path): print(f"Error: CSV file not found at '{args.csv_path}'", file=sys.stderr); sys.exit(1)
    if os.name != 'posix': print("Error: This script requires a POSIX-like OS (Linux, macOS).", file=sys.stderr); sys.exit(1)
    run(csv_path=args.csv_path, max_workers=args.max_workers)