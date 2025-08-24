#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TaskPanel - Controller (with Live Search Navigation)

This module acts as the Controller in the MVC pattern. It now supports live
navigation (up/down/left/right) while the search filter is active, allowing users
to inspect results without exiting search mode. It also features a more intuitive,
two-step escape sequence to clear and then exit search.
"""
import argparse
import curses
import os
import re
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
        self.ui_dirty = True

        # State for search functionality
        self.is_search_mode = False
        self.search_query = ""
        self.filtered_task_indices = []

        # Initialize UI settings
        curses.curs_set(0)
        self.stdscr.nodelay(1)
        setup_colors()
        self.model.load_tasks_from_csv()
        self._apply_search_filter()

        # Map key presses to handler methods
        self.key_handlers = {
            ord('q'): self._handle_quit,
            ord('d'): self._handle_toggle_debug,
            ord('/'): self._handle_enter_search_mode,
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
        
        # CORRECTED: Define keys that are active during search mode for navigation
        self.search_nav_keys = {
            curses.KEY_UP, curses.KEY_DOWN, curses.KEY_LEFT, curses.KEY_RIGHT,
            curses.KEY_HOME, curses.KEY_END, curses.KEY_PPAGE, curses.KEY_NPAGE,
            ord('['), ord(']'), ord('{'), ord('}'),
        }

    # --- Core Application Logic (Unchanged) ---
    def start_initial_tasks(self):
        print(f"Submitting tasks to a pool of {self.max_workers} worker(s)...")
        for i, task in enumerate(self.model.tasks):
            with self.model.state_lock:
                first_step_to_run = -1
                for j, step in enumerate(task.steps):
                    if step.status != Status.SUCCESS: first_step_to_run = j; break
                if first_step_to_run != -1:
                    task.run_counter += 1
                    self.executor.submit(self.model.run_task_row, i, task.run_counter, first_step_to_run)

    def _reset_scroll_states(self):
        self.view_state.log_scroll_offset = 0
        self.view_state.debug_scroll_offset = 0

    # --- Search Handlers (Unchanged) ---
    def _handle_enter_search_mode(self):
        self.is_search_mode = True
        self.search_query = ""
        curses.curs_set(1)
        self.ui_dirty = True

    def _handle_exit_search_mode(self, apply_filter=True):
        self.is_search_mode = False
        curses.curs_set(0)
        if not apply_filter: self.search_query = ""
        self._apply_search_filter()

    def _apply_search_filter(self):
        self.filtered_task_indices = []
        if not self.search_query:
            self.filtered_task_indices = list(range(len(self.model.tasks)))
        else:
            try:
                pattern = re.compile(self.search_query, re.IGNORECASE)
                for i, task in enumerate(self.model.tasks):
                    if pattern.search(task.name): self.filtered_task_indices.append(i)
            except re.error: pass
        self.view_state.selected_row = 0
        self.view_state.top_row = 0
        self._reset_scroll_states()
        self.ui_dirty = True
        
    # --- Input Handlers (Unchanged) ---
    # These now correctly operate on the filtered list, so no changes are needed here.
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
        if not self.filtered_task_indices: return
        h, w = self.stdscr.getmaxyx(); layout = calculate_layout_dimensions(w, self.model, h, self.view_state.debug_panel_visible)
        num_visible_tasks = len(self.filtered_task_indices)
        self.view_state.selected_row = min(num_visible_tasks - 1, self.view_state.selected_row + 1)
        if layout['task_list_h'] > 0: self.view_state.top_row = max(self.view_state.top_row, self.view_state.selected_row - layout['task_list_h'] + 1)
        self._reset_scroll_states()
    def _handle_nav_left(self):
        self.view_state.selected_col = max(-1, self.view_state.selected_col - 1)
        self.view_state.left_most_step = min(self.view_state.left_most_step, max(0, self.view_state.selected_col))
        self._reset_scroll_states()
    def _handle_nav_right(self):
        if not self.filtered_task_indices: return
        original_task_index = self.filtered_task_indices[self.view_state.selected_row]
        task = self.model.tasks[original_task_index]
        if not task.steps: return
        h, w = self.stdscr.getmaxyx(); layout = calculate_layout_dimensions(w, self.model, h, self.view_state.debug_panel_visible)
        max_col = len(task.steps) - 1
        self.view_state.selected_col = min(max_col, self.view_state.selected_col + 1)
        if self.view_state.selected_col >= self.view_state.left_most_step + layout['num_visible_steps']:
            self.view_state.left_most_step = self.view_state.selected_col - layout['num_visible_steps'] + 1
        self._reset_scroll_states()
    def _handle_nav_home(self):
        self.view_state.selected_row, self.view_state.top_row = 0, 0; self._reset_scroll_states()
    def _handle_nav_end(self):
        if not self.filtered_task_indices: return
        h, w = self.stdscr.getmaxyx(); layout = calculate_layout_dimensions(w, self.model, h, self.view_state.debug_panel_visible)
        num_visible_tasks = len(self.filtered_task_indices)
        self.view_state.selected_row = num_visible_tasks - 1
        if layout['task_list_h'] > 0: self.view_state.top_row = max(0, self.view_state.selected_row - layout['task_list_h'] + 1)
        self._reset_scroll_states()
    def _handle_nav_page_up(self):
        h, w = self.stdscr.getmaxyx(); layout = calculate_layout_dimensions(w, self.model, h, self.view_state.debug_panel_visible)
        page_size = layout.get('task_list_h', 1)
        self.view_state.selected_row = max(0, self.view_state.selected_row - page_size)
        self.view_state.top_row = max(0, self.view_state.top_row - page_size)
        self._reset_scroll_states()
    def _handle_nav_page_down(self):
        if not self.filtered_task_indices: return
        h, w = self.stdscr.getmaxyx(); layout = calculate_layout_dimensions(w, self.model, h, self.view_state.debug_panel_visible)
        page_size = layout.get('task_list_h', 1)
        num_visible_tasks = len(self.filtered_task_indices)
        self.view_state.selected_row = min(num_visible_tasks - 1, self.view_state.selected_row + page_size)
        if page_size > 0: self.view_state.top_row = min(max(0, num_visible_tasks - page_size), self.view_state.top_row + page_size)
        self._reset_scroll_states()
    def _handle_rerun(self):
        vs = self.view_state
        if vs.selected_col >= 0 and self.filtered_task_indices:
            original_task_index = self.filtered_task_indices[vs.selected_row]
            task = self.model.tasks[original_task_index]
            if vs.selected_col < len(task.steps):
                is_rerun_allowed = all(task.steps[i].status == Status.SUCCESS for i in range(vs.selected_col))
                if is_rerun_allowed:
                    self.model._log_debug_unsafe(original_task_index, vs.selected_col, "'r' key pressed. Rerun allowed.")
                    self.model.rerun_task_from_step(self.executor, original_task_index, vs.selected_col)
                else:
                    curses.flash()
                    self.model._log_debug_unsafe(original_task_index, vs.selected_col, "Rerun blocked: Preceding step not SUCCESS.")
    def _handle_kill(self):
        vs = self.view_state
        if self.filtered_task_indices:
            original_task_index = self.filtered_task_indices[vs.selected_row]
            if self.model.tasks[original_task_index].steps:
                self.model._log_debug_unsafe(original_task_index, 0, "'k' key pressed for this task.")
            self.model.kill_task_row(original_task_index)

    # --- Main Input and Event Loop (Corrected for live search) ---
    def process_input(self):
        """Processes user input, now allowing navigation during search."""
        try:
            key = self.stdscr.getch()
        except curses.error:
            key = -1
        if key == -1: return

        self.ui_dirty = True
        
        if self.is_search_mode:
            # --- Search Mode Input Handling ---
            if key in (curses.KEY_ENTER, 10, 13):
                self._handle_exit_search_mode(apply_filter=True)
            elif key == 27: # Escape key
                # CORRECTED: Implement two-step escape for clearing search
                if self.search_query:
                    self.search_query = ""
                    self._apply_search_filter()
                else:
                    self._handle_exit_search_mode(apply_filter=False)
            elif key in (curses.KEY_BACKSPACE, 127):
                self.search_query = self.search_query[:-1]
                self._apply_search_filter()
            elif 32 <= key <= 126: # Printable characters
                self.search_query += chr(key)
                self._apply_search_filter()
            # CORRECTED: Allow navigation keys to work while searching
            elif key in self.search_nav_keys:
                if key in self.key_handlers:
                    self.key_handlers[key]()
        else:
            # --- Normal Mode Input Handling ---
            if key in self.key_handlers:
                self.key_handlers[key]()

    def run_loop(self):
        """The main event loop of the application."""
        self.start_initial_tasks()
        last_state_snapshot = None
        while self.app_running:
            with self.model.state_lock:
                current_state_snapshot = [s.status.value for t in self.model.tasks for s in t.steps]
            if current_state_snapshot != last_state_snapshot:
                self.ui_dirty = True
                last_state_snapshot = current_state_snapshot
            if self.ui_dirty:
                draw_ui(self.stdscr, self.model, self.view_state, 
                        self.filtered_task_indices, self.is_search_mode, self.search_query)
                self.ui_dirty = False
            self.process_input()
            time.sleep(0.05)
            
        # --- Graceful Shutdown ---
        if sys.version_info >= (3, 9): self.executor.shutdown(wait=False, cancel_futures=True)
        else: self.executor.shutdown(wait=False)
        self.stdscr.erase()
        self.stdscr.addstr(0, 0, "Quitting: Cleaning up and saving state...", curses.A_BOLD)
        self.stdscr.refresh()
        self.model.cleanup()
        time.sleep(1)

    # --- Main Entry Point (Unchanged) ---
def run(csv_path: str, max_workers: int):
    app_controller = None
    try:
        def main_wrapper(stdscr):
            nonlocal app_controller
            app_controller = AppController(stdscr, csv_path, max_workers)
            app_controller.run_loop()
        curses.wrapper(main_wrapper)
    except TaskLoadError as e: print(str(e), file=sys.stderr); sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user (Ctrl+C). Saving state and exiting.")
        if app_controller: app_controller.model.cleanup()
    except Exception:
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