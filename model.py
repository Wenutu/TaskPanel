#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TaskPanel - Model (Production-Ready with Separate Log Streams)

This file defines the data structures and core business logic for the task runner.
It is completely independent of the UI (View) and user input handling (Controller).
This represents the "Model" in a Model-View-Controller (MVC) architecture.

Key Robustness Features:
- State file is scoped to the input CSV filename for project isolation.
- State persistence includes a SHA256 hash of the source CSV. If the CSV changes,
  the state is automatically invalidated to prevent data inconsistency.
- Intelligently resumes from state: Tasks interrupted are reset from the point of
  failure, preserving prior SUCCESS steps.
- Logs stdout and stderr to separate, uniquely named files for each step,
  preventing memory overflow and allowing for independent log viewing.
"""
import csv
import json
import os
import signal
import subprocess
import sys
import threading
import time
import hashlib
from collections import deque
from enum import Enum

# --- Enum for Type-Safe Status Management ---
class Status(Enum):
    """Enumeration for task and step statuses for enhanced type safety and clarity."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    KILLED = "KILLED"

# --- Custom Exception for Graceful Error Handling ---
class TaskLoadError(Exception):
    """Custom exception raised for fatal errors during task loading."""
    pass

class TaskModel:
    """Manages all tasks, their states, and the logic for their execution."""
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.state_file_path = f".{os.path.basename(csv_path)}.state.json"
        self.log_dir = f".{os.path.basename(csv_path)}.logs"
        self.tasks = []
        self.dynamic_header = []
        self.state_lock = threading.RLock()

    def _log_debug_unsafe(self, task_index, step_index, message):
        """(UNSAFE) Adds a debug message. Must be called with the lock held."""
        if task_index < len(self.tasks) and self.tasks[task_index]["steps"] and step_index < len(self.tasks[task_index]["steps"]):
            step = self.tasks[task_index]["steps"][step_index]
            step["debug_log"].append(f"[{time.strftime('%H:%M:%S')}] {message}")

    def _calculate_hash(self, file_path):
        """Calculates the SHA256 hash of a file for integrity checks."""
        sha256 = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except IOError:
            return None

    def load_tasks_from_csv(self):
        """
        Loads tasks from a CSV and applies any previously saved state.
        Raises TaskLoadError on fatal errors instead of exiting directly.
        """
        print(f"Loading tasks from '{self.csv_path}'...")
        os.makedirs(self.log_dir, exist_ok=True)
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                all_rows = [row for row in reader if row and row[0].strip()]
                if not all_rows:
                    return # Handle empty CSV gracefully
                
                longest_row = max(all_rows, key=len)
                cmd_headers = [cmd.strip().split()[0].split('/')[-1] for cmd in longest_row[2:]] if len(longest_row) > 2 else []
                self.dynamic_header = ["TaskName", "Info"] + cmd_headers
                
                for line_num, row in enumerate(all_rows, 1):
                    task_name, info = (row[0].strip(), row[1].strip()) if len(row) > 1 else (row[0].strip(), "")
                    commands = [cmd for cmd in row[2:] if cmd.strip()]
                    
                    safe_name = "".join(c if c.isalnum() else "_" for c in task_name)
                    task_log_path = os.path.join(self.log_dir, f"{line_num}_{safe_name}")
                    os.makedirs(task_log_path, exist_ok=True)
                    
                    steps = []
                    for i, cmd in enumerate(commands):
                        log_base = os.path.join(task_log_path, f"step{i}")
                        steps.append({"command": cmd, "status": Status.PENDING, "process": None,
                                      "log_path_stdout": f"{log_base}.stdout.log",
                                      "log_path_stderr": f"{log_base}.stderr.log",
                                      "start_time": None, "debug_log": deque(maxlen=50)})
                    
                    self.tasks.append({"id": line_num, "name": task_name, "info": info, "steps": steps, "run_counter": 0})
            print(f"Loaded {len(self.tasks)} tasks successfully.")
            self._resume_state()
        except FileNotFoundError:
            raise TaskLoadError(f"FATAL: The file '{self.csv_path}' was not found.")
        except Exception as e:
            raise TaskLoadError(f"FATAL: Error loading tasks from '{self.csv_path}': {e}")

    def _resume_state(self):
        """If a state file exists and matches the CSV hash, load it intelligently."""
        if not os.path.exists(self.state_file_path):
            print("No state file found. Starting fresh.")
            return
        print(f"Found state file: {self.state_file_path}. Verifying integrity...")
        try:
            with open(self.state_file_path, 'r') as f: saved_data = json.load(f)
            current_hash = self._calculate_hash(self.csv_path)
            if current_hash != saved_data.get("source_csv_sha256"):
                print(f"Warning: '{self.csv_path}' has changed. Discarding old state.")
                os.remove(self.state_file_path)
                return
            print("Integrity check passed. Resuming state.")
            with self.state_lock:
                task_map = {task['id']: task for task in self.tasks}
                for task_state in saved_data.get("tasks", []):
                    task_id = task_state.get('id')
                    if task_id in task_map:
                        task = task_map[task_id]
                        if task['name'] != task_state.get('name'):
                             print(f"  - Warning: Skipping state for task ID {task_id}, name changed from '{task_state.get('name')}' to '{task['name']}'.")
                             continue
                        saved_steps = task_state.get('steps', [])
                        interrupted_at = -1
                        for i, s in enumerate(saved_steps):
                            # Resume from RUNNING or KILLED states
                            if s.get('status') in [Status.RUNNING.value, Status.KILLED.value]:
                                interrupted_at = i
                                break
                        if interrupted_at != -1:
                            print(f"  - Task '{task['name']}' (ID: {task_id}) was interrupted. Resuming from step {interrupted_at}.")
                            for i in range(interrupted_at):
                                if i < len(task['steps']) and i < len(saved_steps):
                                    task['steps'][i]['status'] = Status(saved_steps[i].get('status', Status.PENDING.value))
                        else:
                            for i, saved_step in enumerate(saved_steps):
                                if i < len(task['steps']):
                                    task['steps'][i]['status'] = Status(saved_step.get('status', Status.PENDING.value))
        except (json.JSONDecodeError, IOError, KeyError) as e:
            print(f"Warning: Could not parse state file '{self.state_file_path}'. Starting fresh. Error: {e}")

    def persist_state(self):
        """Saves a minimal state of all tasks and the CSV hash using an atomic write."""
        print("\nPersisting state...")
        state_to_save = []
        with self.state_lock:
            for task in self.tasks:
                # ### BUG FIX: Changed a dictionary comprehension to a list comprehension ###
                # This ensures that a list of step statuses is saved, not just the last one.
                task_data = {"id": task['id'], "name": task['name'], "info": task.get('info', ''),
                             "steps": [{"status": s['status'].value} for s in task['steps']]}
                state_to_save.append(task_data)
        final_data = {"source_csv_sha256": self._calculate_hash(self.csv_path), "tasks": state_to_save}
        
        # Atomic write: write to a temporary file, then rename.
        temp_file_path = self.state_file_path + ".tmp"
        try:
            with open(temp_file_path, 'w') as f:
                json.dump(final_data, f, indent=2)
            os.rename(temp_file_path, self.state_file_path)
            print(f"State saved to {self.state_file_path}")
        except (IOError, OSError) as e:
            print(f"\nError: Could not write state to file '{self.state_file_path}'. Error: {e}")
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    def _kill_process_group(self, task_index, step_index, process):
        """Safely terminates a process and its entire process group."""
        if process and process.poll() is None:
            try:
                pgid = os.getpgid(process.pid)
                with self.state_lock: self._log_debug_unsafe(task_index, step_index, f"Killing process group {pgid}...")
                os.killpg(pgid, signal.SIGTERM); process.wait(timeout=2)
            except (ProcessLookupError, PermissionError):
                with self.state_lock: self._log_debug_unsafe(task_index, step_index, f"PGID for PID {process.pid} already gone.")
            except subprocess.TimeoutExpired:
                with self.state_lock: self._log_debug_unsafe(task_index, step_index, f"PG unresponsive, sending SIGKILL.")
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)

    def run_task_row(self, task_index, run_counter, start_step_index=0):
        """Executes the steps for a task, logging output directly to separate files."""
        for i in range(start_step_index, len(self.tasks[task_index]["steps"])):
            step = self.tasks[task_index]["steps"][i]
            with self.state_lock:
                if self.tasks[task_index]['run_counter'] != run_counter:
                    self._log_debug_unsafe(task_index, i, f"Worker with stale run_counter ({run_counter}) exiting.")
                    return
                if step['status'] != Status.PENDING:
                    self._log_debug_unsafe(task_index, i, f"Skipping step already in state {step['status'].value}.")
                    continue
                step["status"] = Status.RUNNING; step["start_time"] = time.time()
                self._log_debug_unsafe(task_index, i, f"Starting step (run_counter {run_counter}).")
            
            try:
                with open(step['log_path_stdout'], 'wb') as stdout_log, \
                     open(step['log_path_stderr'], 'wb') as stderr_log:
                    # Create a new process group to ensure child processes can be killed reliably.
                    popen_kwargs = {"shell": True, "stdout": stdout_log, "stderr": stderr_log, "preexec_fn": os.setsid}
                    process = subprocess.Popen(step["command"], **popen_kwargs)
                    
                    with self.state_lock:
                        if self.tasks[task_index]['run_counter'] != run_counter: self._kill_process_group(task_index, i, process); return
                        step["process"] = process
                        self._log_debug_unsafe(task_index, i, f"Process started PID: {process.pid}.")
                    
                    process.wait()
                
                with self.state_lock:
                    if self.tasks[task_index]['run_counter'] != run_counter: return
                    duration = time.time() - step["start_time"] if step.get("start_time") else 0
                    step["start_time"] = None
                    # Only change status if it wasn't externally modified (e.g., by 'kill').
                    if step["status"] == Status.RUNNING:
                        step["status"] = Status.SUCCESS if process.returncode == 0 else Status.FAILED
                    self._log_debug_unsafe(task_index, i, f"Process finished code {process.returncode}. Status: {step['status'].value}. Duration: {duration:.2f}s.")
                    if step["status"] != Status.SUCCESS:
                        for j in range(i + 1, len(self.tasks[task_index]["steps"])): self.tasks[task_index]["steps"][j]["status"] = Status.SKIPPED
                        break
            except Exception as e:
                with self.state_lock:
                    if self.tasks[task_index]['run_counter'] != run_counter: return
                    step["status"] = Status.FAILED; step["start_time"] = None
                    self._log_debug_unsafe(task_index, i, f"CRITICAL ERROR: {e}")
                    try:
                        with open(step['log_path_stderr'], 'ab') as stderr_log:
                            stderr_log.write(f"\n\n--- TASKPANEL CRITICAL ERROR ---\n{str(e)}\n".encode('utf-8'))
                    except IOError as io_err:
                        print(f"FATAL: Could not write critical error to log file {step['log_path_stderr']}: {io_err}", file=sys.stderr)
                break

    def rerun_task_from_step(self, executor, task_index, start_step_index):
        with self.state_lock:
            task = self.tasks[task_index]
            self._log_debug_unsafe(task_index, start_step_index, "RERUN triggered.")
            task['run_counter'] += 1
            new_run_counter = task['run_counter']
            self._log_debug_unsafe(task_index, start_step_index, f"New run_counter is {new_run_counter}.")
            for i in range(start_step_index, len(task["steps"])):
                step_to_reset = task["steps"][i]
                if step_to_reset["process"]: self._kill_process_group(task_index, i, step_to_reset["process"])
                if step_to_reset["status"] == Status.RUNNING: step_to_reset["status"] = Status.KILLED
                step_to_reset["status"] = Status.PENDING; step_to_reset["start_time"] = None
                
                try: # Clean up old logs for the rerun
                    if os.path.exists(step_to_reset['log_path_stdout']): os.remove(step_to_reset['log_path_stdout'])
                    if os.path.exists(step_to_reset['log_path_stderr']): os.remove(step_to_reset['log_path_stderr'])
                    self._log_debug_unsafe(task_index, i, f"Removed old log files for step {i}")
                except OSError as e:
                     self._log_debug_unsafe(task_index, i, f"Error removing log files: {e}")
        executor.submit(self.run_task_row, task_index, new_run_counter, start_step_index)

    def kill_task_row(self, task_index):
        with self.state_lock:
            task = self.tasks[task_index]
            self._log_debug_unsafe(task_index, 0, "KILL TASK triggered.")
            task['run_counter'] += 1
            kill_point_found = False
            for i, step in enumerate(task["steps"]):
                if step["status"] == Status.RUNNING:
                    if step["process"]: self._kill_process_group(task_index, i, step["process"])
                    step["status"] = Status.KILLED
                    if step.get("start_time"): self._log_debug_unsafe(task_index, i, f"KILLED after {time.time() - step['start_time']:.2f}s.")
                    step["start_time"] = None
                    kill_point_found = True
                elif step["status"] == Status.PENDING and kill_point_found:
                    step["status"] = Status.SKIPPED

    def cleanup(self):
        """Gracefully shuts down all running processes before exiting."""
        with self.state_lock:
            print("\nCleaning up running processes...")
            for task_index, task in enumerate(self.tasks):
                task['run_counter'] += 1 # Invalidate any running workers
                for step_index, step in enumerate(task["steps"]):
                    if step["process"]: self._kill_process_group(task_index, step_index, step["process"])
        self.persist_state()