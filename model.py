#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TaskPanel - Model (Python 3.6 Compatible)

This module defines the data structures and core business logic for the task runner.
It is completely independent of the UI, representing the "Model" in an MVC architecture.
This version uses standard classes for Python 3.6 compatibility, incorporates pathlib
for robust path management, and features more precise exception handling.
"""
import csv
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from enum import Enum
from pathlib import Path
from typing import List, Deque, Any, Optional

# --- Constants ---
STATE_FILE_SUFFIX = ".state.json"
LOG_DIR_SUFFIX = ".logs"

# --- Enums and Exceptions ---
class Status(Enum):
    """Enumeration for task and step statuses for enhanced type safety and clarity."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    KILLED = "KILLED"

class TaskLoadError(Exception):
    """Custom exception raised for fatal errors during task loading."""
    pass

# --- Data Structures (Standard Classes for Python 3.6) ---
class Step:
    """Represents a single command to be executed within a task."""
    def __init__(self, command: str, log_path_stdout: str, log_path_stderr: str):
        self.command = command
        self.status = Status.PENDING
        self.process = None  # type: Optional[subprocess.Popen]
        self.log_path_stdout = log_path_stdout
        self.log_path_stderr = log_path_stderr
        self.start_time = None  # type: Optional[float]
        self.debug_log = deque(maxlen=50) # type: Deque[str]

    def __repr__(self):
        return f"Step(command='{self.command[:30]}...', status={self.status.value})"

class Task:
    """Represents a full task, composed of an ordered sequence of steps."""
    def __init__(self, id: int, name: str, info: str, steps: List[Step]):
        self.id = id
        self.name = name
        self.info = info
        self.steps = steps
        self.run_counter = 0

    def __repr__(self):
        return f"Task(id={self.id}, name='{self.name}', steps={len(self.steps)})"

class TaskModel:
    """Manages all tasks, their state, and the logic for their execution."""
    def __init__(self, csv_path: str):
        self.csv_path = Path(csv_path)
        base_name = self.csv_path.name
        self.state_file_path = self.csv_path.parent / f".{base_name}{STATE_FILE_SUFFIX}"
        self.log_dir = self.csv_path.parent / f".{base_name}{LOG_DIR_SUFFIX}"
        self.tasks = []  # type: List[Task]
        self.dynamic_header = []  # type: List[str]
        self.state_lock = threading.RLock()

    def _log_debug_unsafe(self, task_index: int, step_index: int, message: str):
        """(UNSAFE) Adds a debug message. Must be called with the state_lock held."""
        if 0 <= task_index < len(self.tasks) and 0 <= step_index < len(self.tasks[task_index].steps):
            step = self.tasks[task_index].steps[step_index]
            step.debug_log.append(f"[{time.strftime('%H:%M:%S')}] {message}")

    def _calculate_hash(self, file_path: Path) -> Optional[str]:
        """Calculates the SHA256 hash of a file for integrity checks."""
        sha256 = hashlib.sha256()
        try:
            with file_path.open('rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except IOError:
            return None

    def load_tasks_from_csv(self):
        """
        Loads tasks from the specified CSV file and applies any previously saved state.
        Raises TaskLoadError on fatal file or parsing errors.
        """
        print(f"Loading tasks from '{self.csv_path}'...")
        try:
            self.log_dir.mkdir(exist_ok=True)
            with self.csv_path.open('r', encoding='utf-8') as f:
                reader = csv.reader(f)
                all_rows = [row for row in reader if row and row[0].strip()]
                if not all_rows: return

                longest_row = max(all_rows, key=len)
                if len(longest_row) > 2:
                    command_definitions = longest_row[2:]
                    cmd_headers = [os.path.basename(cmd.strip().split()[0]) for cmd in command_definitions]
                else:
                    cmd_headers = []
                self.dynamic_header = ["TaskName", "Info"] + cmd_headers

                for line_num, row in enumerate(all_rows, 1):
                    task_name, info = (row[0].strip(), row[1].strip()) if len(row) > 1 else (row[0].strip(), "")
                    commands = [cmd for cmd in row[2:] if cmd.strip()]
                    safe_name = "".join(c if c.isalnum() else "_" for c in task_name)
                    task_log_path = self.log_dir / f"{line_num}_{safe_name}"
                    task_log_path.mkdir(exist_ok=True)

                    steps = []
                    for i, cmd in enumerate(commands):
                        log_base = task_log_path / f"step{i}"
                        steps.append(Step(command=cmd,
                                          log_path_stdout=str(f"{log_base}.stdout.log"),
                                          log_path_stderr=str(f"{log_base}.stderr.log")))
                    self.tasks.append(Task(id=line_num, name=task_name, info=info, steps=steps))
            print(f"Loaded {len(self.tasks)} tasks successfully.")
            self._resume_state()
        except FileNotFoundError:
            raise TaskLoadError(f"FATAL: The file '{self.csv_path}' was not found.")
        except (csv.Error, IndexError) as e:
            raise TaskLoadError(f"FATAL: Error parsing CSV file '{self.csv_path}': {e}")
        except IOError as e:
            raise TaskLoadError(f"FATAL: I/O error reading '{self.csv_path}': {e}")

    def _resume_state(self):
        """If a valid state file exists, intelligently load task statuses from it."""
        if not self.state_file_path.exists():
            print("No state file found. Starting fresh.")
            return
        print(f"Found state file: {self.state_file_path}. Verifying integrity...")
        try:
            with self.state_file_path.open('r') as f: saved_data = json.load(f)
            current_hash = self._calculate_hash(self.csv_path)
            if current_hash != saved_data.get("source_csv_sha256"):
                print(f"Warning: '{self.csv_path}' has changed. Discarding old state.")
                os.remove(str(self.state_file_path))
                return

            print("Integrity check passed. Resuming state.")
            with self.state_lock:
                task_map = {task.id: task for task in self.tasks}
                for task_state in saved_data.get("tasks", []):
                    task_id = task_state.get('id')
                    if task_id in task_map:
                        task = task_map[task_id]
                        if task.name != task_state.get('name'):
                             print(f"  - Warning: Skipping state for task ID {task_id}, name changed.")
                             continue
                        saved_steps = task_state.get('steps', [])
                        interrupted_at = -1
                        for i, s in enumerate(saved_steps):
                            if s.get('status') in [Status.RUNNING.value, Status.KILLED.value]:
                                interrupted_at = i
                                break
                        if interrupted_at != -1:
                            print(f"  - Task '{task.name}' (ID: {task_id}) was interrupted. Resuming from step {interrupted_at}.")
                            for i in range(interrupted_at):
                                if i < len(task.steps) and i < len(saved_steps):
                                    task.steps[i].status = Status(saved_steps[i].get('status', Status.PENDING.value))
                        else:
                            for i, saved_step in enumerate(saved_steps):
                                if i < len(task.steps):
                                    task.steps[i].status = Status(saved_step.get('status', Status.PENDING.value))
        except (json.JSONDecodeError, IOError, KeyError) as e:
            print(f"Warning: Could not parse state file '{self.state_file_path}'. Starting fresh. Error: {e}")

    def persist_state(self):
        """Saves the minimal required state of all tasks using an atomic write."""
        print("\nPersisting state...")
        state_to_save = []
        with self.state_lock:
            for task in self.tasks:
                task_data = { "id": task.id, "name": task.name, "info": task.info, "steps": [{"status": s.status.value} for s in task.steps] }
                state_to_save.append(task_data)
        final_data = {"source_csv_sha256": self._calculate_hash(self.csv_path), "tasks": state_to_save}

        temp_file_path = self.state_file_path.with_suffix(self.state_file_path.suffix + ".tmp")
        try:
            with temp_file_path.open('w') as f:
                json.dump(final_data, f, indent=2)
            os.rename(str(temp_file_path), str(self.state_file_path))
            print(f"State saved to {self.state_file_path}")
        except (IOError, OSError) as e:
            print(f"\nError: Could not write state to file '{self.state_file_path}'. Error: {e}")
            if temp_file_path.exists(): temp_file_path.unlink()

    def _kill_process_group(self, task_index: int, step_index: int, process: subprocess.Popen):
        """Safely terminates a process and its entire process group."""
        if process.poll() is None:
            try:
                pgid = os.getpgid(process.pid)
                with self.state_lock: self._log_debug_unsafe(task_index, step_index, f"Killing process group {pgid}...")
                os.killpg(pgid, signal.SIGTERM)
                process.wait(timeout=2)
            except (ProcessLookupError, PermissionError):
                with self.state_lock: self._log_debug_unsafe(task_index, step_index, f"PGID for PID {process.pid} already gone.")
            except subprocess.TimeoutExpired:
                with self.state_lock: self._log_debug_unsafe(task_index, step_index, "PG unresponsive, sending SIGKILL.")
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)

    def run_task_row(self, task_index: int, run_counter: int, start_step_index: int = 0):
        """Executes the steps for a given task, starting from a specific step."""
        task = self.tasks[task_index]
        for i in range(start_step_index, len(task.steps)):
            step = task.steps[i]
            with self.state_lock:
                if task.run_counter != run_counter:
                    self._log_debug_unsafe(task_index, i, f"Worker with stale run_counter ({run_counter}) exiting.")
                    return
                if step.status != Status.PENDING:
                    self._log_debug_unsafe(task_index, i, f"Skipping step already in state {step.status.value}.")
                    continue
                step.status = Status.RUNNING
                step.start_time = time.time()
                self._log_debug_unsafe(task_index, i, f"Starting step (run_counter {run_counter}).")

            try:
                with open(step.log_path_stdout, 'wb') as stdout_log, open(step.log_path_stderr, 'wb') as stderr_log:
                    popen_kwargs = {"shell": True, "stdout": stdout_log, "stderr": stderr_log, "preexec_fn": os.setsid}
                    process = subprocess.Popen(step.command, **popen_kwargs)

                    with self.state_lock:
                        if task.run_counter != run_counter: self._kill_process_group(task_index, i, process); return
                        step.process = process
                        self._log_debug_unsafe(task_index, i, f"Process started PID: {process.pid}.")

                    process.wait()

                with self.state_lock:
                    if task.run_counter != run_counter: return
                    duration = time.time() - step.start_time if step.start_time else 0
                    step.start_time = None
                    if step.status == Status.RUNNING:
                        step.status = Status.SUCCESS if process.returncode == 0 else Status.FAILED
                    self._log_debug_unsafe(task_index, i, f"Process finished code {process.returncode}. Status: {step.status.value}. Duration: {duration:.2f}s.")
                    if step.status != Status.SUCCESS:
                        for j in range(i + 1, len(task.steps)): task.steps[j].status = Status.SKIPPED
                        break
            except FileNotFoundError as e:
                with self.state_lock:
                    if task.run_counter != run_counter: return
                    step.status = Status.FAILED
                    step.start_time = None
                    err_msg = f"CRITICAL ERROR: Command not found. Ensure '{step.command.split()[0]}' is in your PATH. Details: {e}"
                    self._log_debug_unsafe(task_index, i, err_msg)
                    try:
                        with open(step.log_path_stderr, 'ab') as f: f.write(f"\n--- TASKPANEL CRITICAL ERROR ---\n{err_msg}\n".encode())
                    except IOError: pass
                break
            except (OSError, subprocess.SubprocessError) as e:
                with self.state_lock:
                    if task.run_counter != run_counter: return
                    step.status = Status.FAILED
                    step.start_time = None
                    err_msg = f"CRITICAL ERROR starting process: {e}"
                    self._log_debug_unsafe(task_index, i, err_msg)
                    try:
                        with open(step.log_path_stderr, 'ab') as f: f.write(f"\n--- TASKPANEL CRITICAL ERROR ---\n{err_msg}\n".encode())
                    except IOError: pass
                break
    
    def rerun_task_from_step(self, executor, task_index: int, start_step_index: int):
        """Resets a task from a specific step and submits it for execution."""
        with self.state_lock:
            task = self.tasks[task_index]
            self._log_debug_unsafe(task_index, start_step_index, "RERUN triggered.")
            task.run_counter += 1
            new_run_counter = task.run_counter
            self._log_debug_unsafe(task_index, start_step_index, f"New run_counter is {new_run_counter}.")

            for i in range(start_step_index, len(task.steps)):
                step_to_reset = task.steps[i]
                if step_to_reset.process: self._kill_process_group(task_index, i, step_to_reset.process)
                if step_to_reset.status == Status.RUNNING: step_to_reset.status = Status.KILLED
                step_to_reset.status = Status.PENDING
                step_to_reset.start_time = None
                try:
                    if os.path.exists(step_to_reset.log_path_stdout): os.remove(step_to_reset.log_path_stdout)
                    if os.path.exists(step_to_reset.log_path_stderr): os.remove(step_to_reset.log_path_stderr)
                    self._log_debug_unsafe(task_index, i, f"Removed old log files for step {i}")
                except OSError as e:
                     self._log_debug_unsafe(task_index, i, f"Error removing log files: {e}")
        executor.submit(self.run_task_row, task_index, new_run_counter, start_step_index)

    def kill_task_row(self, task_index: int):
        """Stops a running task and marks subsequent steps as skipped."""
        with self.state_lock:
            task = self.tasks[task_index]
            self._log_debug_unsafe(task_index, 0, "KILL TASK triggered.")
            task.run_counter += 1
            kill_point_found = False
            for i, step in enumerate(task.steps):
                if step.status == Status.RUNNING:
                    if step.process: self._kill_process_group(task_index, i, step.process)
                    step.status = Status.KILLED
                    if step.start_time: self._log_debug_unsafe(task_index, i, f"KILLED after {time.time() - step.start_time:.2f}s.")
                    step.start_time = None
                    kill_point_found = True
                elif step.status == Status.PENDING and kill_point_found:
                    step.status = Status.SKIPPED
    
    def cleanup(self):
        """Gracefully shuts down all running processes before exiting."""
        with self.state_lock:
            print("\nCleaning up running processes...")
            for task_index, task in enumerate(self.tasks):
                task.run_counter += 1
                for step_index, step in enumerate(task.steps):
                    if step.process: self._kill_process_group(task_index, step_index, step.process)
        self.persist_state()