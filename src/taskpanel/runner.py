#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TaskPanel - Controller (with Live Search Navigation, Optimized)

This module acts as the Controller in the MVC pattern.
OPTIMIZED with layout caching to improve rendering performance and handle resizes.
"""
import curses
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from .model import Status, TaskLoadError, TaskModel
from .view import ViewState, draw_ui, setup_colors

# Constants for timing and key codes
MAIN_LOOP_SLEEP_S = 0.05
UI_REFRESH_INTERVAL_S = 0.5
SHUTDOWN_CLEANUP_WAIT_S = 1
ENTER_KEYS = (curses.KEY_ENTER, 10, 13)
BACKSPACE_KEYS = (curses.KEY_BACKSPACE, 127)


class AppController:
    """Manages the application's main loop, user input, and state transitions."""

    def __init__(self, stdscr, csv_path: str, max_workers: int, title: str):
        self.stdscr = stdscr
        self.max_workers = max_workers
        self.title = title
        self.model = TaskModel(csv_path)
        self.view_state = ViewState()
        self.app_running = True
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.ui_dirty = True
        self.is_search_mode = False
        self.search_query = ""
        self.filtered_task_indices = []

        curses.curs_set(0)
        self.stdscr.nodelay(1)
        setup_colors()
        self.model.load_tasks_from_csv()
        self._apply_search_filter()

        self.key_handlers = {
            ord("q"): self._handle_quit,
            ord("d"): self._handle_toggle_debug,
            ord("/"): self._handle_enter_search_mode,
            curses.KEY_UP: self._handle_nav_up,
            curses.KEY_DOWN: self._handle_nav_down,
            curses.KEY_LEFT: self._handle_nav_left,
            curses.KEY_RIGHT: self._handle_nav_right,
            curses.KEY_HOME: self._handle_nav_home,
            curses.KEY_END: self._handle_nav_end,
            curses.KEY_PPAGE: self._handle_nav_page_up,
            curses.KEY_NPAGE: self._handle_nav_page_down,
            ord("r"): self._handle_rerun,
            ord("k"): self._handle_kill,
            ord("["): self._handle_scroll_log_up,
            ord("]"): self._handle_scroll_log_down,
            ord("{"): self._handle_scroll_debug_up,
            ord("}"): self._handle_scroll_debug_down,
            # OPTIMIZATION: Handle terminal resize event
            curses.KEY_RESIZE: self._handle_resize,
        }

        self.search_nav_keys = {
            curses.KEY_UP,
            curses.KEY_DOWN,
            curses.KEY_LEFT,
            curses.KEY_RIGHT,
            curses.KEY_HOME,
            curses.KEY_END,
            curses.KEY_PPAGE,
            curses.KEY_NPAGE,
            ord("["),
            ord("]"),
            ord("{"),
            ord("}"),
        }

    def start_initial_tasks(self):
        print("Checking for tasks to auto-resume...")
        for i, task in enumerate(self.model.tasks):
            first_step_to_run = -1
            all_done = True
            for j, step in enumerate(task.steps):
                if step and step.status != Status.SUCCESS:
                    first_step_to_run, all_done = j, False
                    break
            if not all_done and first_step_to_run != -1:
                print(f"  - Resuming task '{task.name}' from step {first_step_to_run}.")
                self.executor.submit(
                    self.model.run_task_row, i, task.run_counter, first_step_to_run
                )

    def _reset_scroll_states(self):
        self.view_state.log_scroll_offset = 0
        self.view_state.debug_scroll_offset = 0
        self.view_state.log_cache = {}

    def _handle_enter_search_mode(self):
        self.is_search_mode, self.search_query = True, ""
        curses.curs_set(1)
        self.ui_dirty = True

    def _handle_exit_search_mode(self, apply_filter=True):
        self.is_search_mode = False
        curses.curs_set(0)
        if not apply_filter:
            self.search_query = ""
        self._apply_search_filter()

    def _apply_search_filter(self):
        if not self.search_query:
            self.filtered_task_indices = list(range(len(self.model.tasks)))
        else:
            self.filtered_task_indices = []
            try:
                pattern = re.compile(self.search_query, re.IGNORECASE)
                for i, task in enumerate(self.model.tasks):
                    if pattern.search(task.name):
                        self.filtered_task_indices.append(i)
            except re.error:
                pass
        self.view_state.selected_row = (
            min(self.view_state.selected_row, len(self.filtered_task_indices) - 1)
            if self.filtered_task_indices
            else 0
        )
        self.view_state.top_row = 0
        self._reset_scroll_states()
        self.ui_dirty = True

    def _handle_quit(self):
        self.app_running = False

    # OPTIMIZATION: New handler for resize events
    def _handle_resize(self):
        self.view_state.layout_dirty = True
        self.ui_dirty = True

    def _handle_toggle_debug(self):
        self.view_state.debug_panel_visible = not self.view_state.debug_panel_visible
        self.view_state.layout_dirty = True  # Layout has changed

    def _handle_scroll_log_up(self):
        self.view_state.log_scroll_offset = max(
            0, self.view_state.log_scroll_offset - 1
        )

    def _handle_scroll_log_down(self):
        self.view_state.log_scroll_offset += 1

    def _handle_scroll_debug_up(self):
        self.view_state.debug_scroll_offset = max(
            0, self.view_state.debug_scroll_offset - 1
        )

    def _handle_scroll_debug_down(self):
        self.view_state.debug_scroll_offset += 1

    def _handle_nav_up(self):
        self.view_state.selected_row = max(0, self.view_state.selected_row - 1)
        self.view_state.top_row = min(
            self.view_state.top_row, self.view_state.selected_row
        )
        self._reset_scroll_states()

    def _handle_nav_down(self):
        if not self.filtered_task_indices:
            return
        num_visible_tasks = len(self.filtered_task_indices)
        self.view_state.selected_row = min(
            num_visible_tasks - 1, self.view_state.selected_row + 1
        )
        if (
            self.view_state.cached_layout
            and self.view_state.cached_layout.task_list_h > 0
        ):
            self.view_state.top_row = max(
                self.view_state.top_row,
                self.view_state.selected_row
                - self.view_state.cached_layout.task_list_h
                + 1,
            )
        self._reset_scroll_states()

    def _handle_nav_left(self):
        self.view_state.selected_col = max(-1, self.view_state.selected_col - 1)
        self.view_state.left_most_step = min(
            self.view_state.left_most_step, max(0, self.view_state.selected_col)
        )
        self._reset_scroll_states()

    def _handle_nav_right(self):
        if not self.filtered_task_indices:
            return
        original_task_index = self.filtered_task_indices[self.view_state.selected_row]
        task = self.model.tasks[original_task_index]
        if not task.steps or not self.view_state.cached_layout:
            return
        layout = self.view_state.cached_layout
        max_col = len(task.steps) - 1
        self.view_state.selected_col = min(max_col, self.view_state.selected_col + 1)
        if (
            self.view_state.selected_col
            >= self.view_state.left_most_step + layout.num_visible_steps
        ):
            self.view_state.left_most_step = (
                self.view_state.selected_col - layout.num_visible_steps + 1
            )
        self._reset_scroll_states()

    def _handle_nav_home(self):
        self.view_state.selected_row, self.view_state.top_row = 0, 0
        self._reset_scroll_states()

    def _handle_nav_end(self):
        if not self.filtered_task_indices or not self.view_state.cached_layout:
            return
        layout = self.view_state.cached_layout
        num_visible_tasks = len(self.filtered_task_indices)
        self.view_state.selected_row = num_visible_tasks - 1
        if layout.task_list_h > 0:
            self.view_state.top_row = max(
                0, self.view_state.selected_row - layout.task_list_h + 1
            )
        self._reset_scroll_states()

    def _handle_nav_page_up(self):
        if not self.view_state.cached_layout:
            return
        page_size = self.view_state.cached_layout.task_list_h or 1
        self.view_state.selected_row = max(0, self.view_state.selected_row - page_size)
        self.view_state.top_row = max(0, self.view_state.top_row - page_size)
        self._reset_scroll_states()

    def _handle_nav_page_down(self):
        if not self.filtered_task_indices or not self.view_state.cached_layout:
            return
        layout = self.view_state.cached_layout
        page_size = layout.task_list_h or 1
        num_visible_tasks = len(self.filtered_task_indices)
        self.view_state.selected_row = min(
            num_visible_tasks - 1, self.view_state.selected_row + page_size
        )
        if page_size > 0:
            self.view_state.top_row = min(
                max(0, num_visible_tasks - page_size),
                self.view_state.top_row + page_size,
            )
        self._reset_scroll_states()

    def _handle_rerun(self):
        vs = self.view_state
        if vs.selected_col >= 0 and self.filtered_task_indices:
            original_task_index = self.filtered_task_indices[vs.selected_row]
            task = self.model.tasks[original_task_index]
            if vs.selected_col < len(task.steps):
                step_to_run = task.steps[vs.selected_col]
                if not step_to_run:
                    curses.flash()
                    self.model._log_step_debug(
                        original_task_index,
                        vs.selected_col,
                        "Rerun blocked: Empty step.",
                    )
                    return
                is_rerun_allowed = all(
                    s is None or s.status == Status.SUCCESS
                    for s in task.steps[: vs.selected_col]
                )
                if is_rerun_allowed:
                    self.model._log_step_debug(
                        original_task_index,
                        vs.selected_col,
                        "'r' key pressed. Rerun allowed.",
                    )
                    self.model.rerun_task_from_step(
                        self.executor, original_task_index, vs.selected_col
                    )
                else:
                    curses.flash()
                    self.model._log_step_debug(
                        original_task_index,
                        vs.selected_col,
                        "Rerun blocked: Preceding step not SUCCESS.",
                    )

    def _handle_kill(self):
        if self.filtered_task_indices:
            original_task_index = self.filtered_task_indices[
                self.view_state.selected_row
            ]
            self.model.kill_task_row(original_task_index)

    def process_input(self):
        try:
            key = self.stdscr.getch()
        except curses.error:
            key = -1
        if key == -1:
            return
        self.ui_dirty = True
        if self.is_search_mode:
            if key in ENTER_KEYS:
                self._handle_exit_search_mode(apply_filter=True)
            elif key == 27:
                if self.search_query:
                    self.search_query = ""
                    self._apply_search_filter()
                else:
                    self._handle_exit_search_mode(apply_filter=False)
            elif key in BACKSPACE_KEYS:
                self.search_query = self.search_query[:-1]
                self._apply_search_filter()
            elif 32 <= key <= 126:
                self.search_query += chr(key)
                self._apply_search_filter()
            elif key in self.search_nav_keys and key in self.key_handlers:
                self.key_handlers[key]()
        elif key in self.key_handlers:
            self.key_handlers[key]()

    def run_loop(self):
        try:
            self.start_initial_tasks()
            last_state_snapshot = None
            last_refresh_time = time.time()
            while self.app_running:
                self.view_state.spinner_frame += 1
                with self.model.state_lock:
                    current_state_snapshot = [
                        (s.status.value, s.start_time) if s else None
                        for t in self.model.tasks
                        for s in t.steps
                    ]
                if current_state_snapshot != last_state_snapshot:
                    self.ui_dirty = True
                    last_state_snapshot = current_state_snapshot
                if time.time() - last_refresh_time > UI_REFRESH_INTERVAL_S:
                    self.ui_dirty = True
                if self.ui_dirty:
                    draw_ui(
                        self.stdscr,
                        self.model,
                        self.view_state,
                        self.filtered_task_indices,
                        self.is_search_mode,
                        self.search_query,
                        self.title,
                    )
                    self.ui_dirty = False
                    last_refresh_time = time.time()
                self.process_input()
                time.sleep(MAIN_LOOP_SLEEP_S)
        except KeyboardInterrupt:
            self.app_running = False
            print("\nInterrupted by user (Ctrl+C).")
        finally:
            if sys.version_info >= (3, 9):
                self.executor.shutdown(wait=False, cancel_futures=True)
            else:
                self.executor.shutdown(wait=False)
            self.stdscr.erase()
            self.stdscr.addstr(
                0, 0, "Quitting: Cleaning up and saving state...", curses.A_BOLD
            )
            self.stdscr.refresh()
            self.model.cleanup()
            time.sleep(SHUTDOWN_CLEANUP_WAIT_S)


def run(csv_path: str, max_workers: int, title: str = "TaskPanel"):
    """
    Public function to launch the TaskPanel UI.

    Args:
        csv_path (str): Path to the tasks CSV file.
        max_workers (int): The maximum number of tasks to run in parallel.
        title (str, optional): A custom title for the application window.
                               Defaults to "TaskPanel".
    """
    # --- Argument Validation ---
    if max_workers < 1:
        raise ValueError(
            f"max_workers must be a positive integer, but got {max_workers}"
        )
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Error: CSV file not found at '{csv_path}'")
    if os.name != "posix":
        raise OSError("Error: This script requires a POSIX-like OS (Linux, macOS).")

    try:
        curses.wrapper(
            lambda stdscr: AppController(
                stdscr, csv_path, max_workers, title
            ).run_loop()
        )
    except TaskLoadError as e:
        # Re-raise for the calling script to handle
        raise e
    except KeyboardInterrupt:
        print("\nInterrupted by user (Ctrl+C).")
    except Exception as e:
        import traceback

        try:
            curses.endwin()
        except curses.error:
            pass
        print("\n--- A FATAL ERROR OCCURRED ---", file=sys.stderr)
        traceback.print_exc()
        # Re-raise the original exception after printing details
        raise e
    finally:
        print("TaskPanel has exited.")
