#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TaskPanel - Model (Production-Ready with Hierarchical Logging)

This file defines the data structures and core business logic for the task runner.
It is completely independent of the UI (View) and user input handling (Controller).
This represents the "Model" in a Model-View-Controller (MVC) architecture.

Key Robustness Features:
- State file is scoped to the input CSV filename for project isolation.
- State persistence includes a SHA256 hash of the source CSV. If the CSV changes,
  the state is automatically invalidated to prevent data inconsistency.
- Intelligently resumes from state:
  - Tasks that were interrupted are reset from the point of failure, preserving prior SUCCESS steps.
- Logs stdout/stderr directly to a unique, hierarchical directory structure
  (`.logs/line<N>_<TaskName>/step<I>.log`) to prevent memory overflow and handle duplicate task names.
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

STATUS_PENDING, STATUS_RUNNING, STATUS_SUCCESS, STATUS_FAILED, STATUS_SKIPPED, STATUS_KILLED = \
    "PENDING", "RUNNING", "SUCCESS", "FAILED", "SKIPPED", "KILLED"

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
                while True:
                    chunk = f.read(8192)
                    if not chunk: break
                    sha256.update(chunk)
            return sha256.hexdigest()
        except IOError:
            return None

    def load_tasks_from_csv(self):
        """Loads tasks from a CSV and applies any previously saved state."""
        print(f"Loading tasks from '{self.csv_path}'...")
        os.makedirs(self.log_dir, exist_ok=True)
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                all_rows = [row for row in reader if row and row[0].strip()]
                if not all_rows: raise StopIteration
                
                longest_row = max(all_rows, key=len)
                cmd_headers = [cmd.strip().split()[0].split('/')[-1] for cmd in longest_row[2:]] if len(longest_row) > 2 else []
                self.dynamic_header = ["TaskName", "Info"] + cmd_headers
                
                for line_num, row in enumerate(all_rows, 1):
                    if len(row) < 1: continue
                    task_name, info = row[0].strip(), row[1].strip() if len(row) > 1 else ""
                    commands = [cmd for cmd in row[2:] if cmd.strip()]
                    
                    # Sanitize task name to create a valid directory name
                    safe_name = "".join(c if c.isalnum() else "_" for c in task_name)
                    task_log_dir_name = f"{line_num}_{safe_name}"
                    task_log_path = os.path.join(self.log_dir, task_log_dir_name)
                    os.makedirs(task_log_path, exist_ok=True)
                    
                    steps = []
                    for i, cmd in enumerate(commands):
                        log_filepath = os.path.join(task_log_path, f"step{i}.log")
                        steps.append({"command": cmd, "status": STATUS_PENDING, "process": None,
                                      "log_path": log_filepath, "start_time": None,
                                      "debug_log": deque(maxlen=50)})
                    
                    self.tasks.append({"name": task_name, "info": info, "steps": steps, "run_counter": 0})
            print(f"Loaded {len(self.tasks)} tasks successfully.")
            self._resume_state()
        except Exception as e:
            print(f"FATAL: Error loading tasks from '{self.csv_path}': {e}"); sys.exit(1)

    def _resume_state(self):
        """If a state file exists and matches the CSV hash, load it intelligently."""
        if not os.path.exists(self.state_file_path):
            print("No state file found. Starting fresh.")
            return
        print(f"Found state file: {self.state_file_path}. Verifying integrity...")
        try:
            with open(self.state_file_path, 'r') as f: saved_data = json.load(f)
            current_hash = self._calculate_hash(self.csv_path)
            saved_hash = saved_data.get("source_csv_sha256")
            if current_hash != saved_hash:
                print(f"Warning: '{self.csv_path}' has changed. Discarding old state.")
                os.remove(self.state_file_path)
                return
            print("Integrity check passed. Resuming state.")
            with self.state_lock:
                task_map = {task['name']: task for task in self.tasks}
                for task_state in saved_data.get("tasks", []):
                    task_name = task_state.get('name')
                    if task_name in task_map:
                        task = task_map[task_name]
                        saved_steps = task_state.get('steps', [])
                        interrupted_at = -1
                        for i, s in enumerate(saved_steps):
                            if s.get('status') in [STATUS_RUNNING, STATUS_KILLED]:
                                interrupted_at = i; break
                        if interrupted_at != -1:
                            print(f"  - Task '{task_name}' was interrupted. Resuming from step {interrupted_at}.")
                            for i in range(interrupted_at):
                                if i < len(task['steps']) and i < len(saved_steps):
                                    task['steps'][i]['status'] = saved_steps[i].get('status', STATUS_PENDING)
                            for i in range(interrupted_at, len(task['steps'])):
                                task['steps'][i]['status'] = STATUS_PENDING
                        else:
                            task['info'] = task_state.get('info', task['info'])
                            for i, saved_step in enumerate(saved_steps):
                                if i < len(task['steps']):
                                    task['steps'][i]['status'] = saved_step.get('status', STATUS_PENDING)
        except (json.JSONDecodeError, IOError, KeyError) as e:
            print(f"Warning: Could not read or parse state file '{self.state_file_path}'. Starting fresh. Error: {e}")

    def persist_state(self):
        """Saves a minimal state of all tasks and the CSV hash."""
        print("\nPersisting state...")
        state_to_save = []
        with self.state_lock:
            for task in self.tasks:
                task_data = {"name": task['name'], "info": task.get('info', ''),
                             "steps": [{"status": s['status']} for s in task['steps']]}
                state_to_save.append(task_data)
        final_data = {"source_csv_sha256": self._calculate_hash(self.csv_path), "tasks": state_to_save}
        try:
            with open(self.state_file_path, 'w') as f: json.dump(final_data, f, indent=2)
            print(f"State saved to {self.state_file_path}")
        except IOError as e:
            print(f"\nError: Could not write state to file '{self.state_file_path}'. Error: {e}")

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
                os.killpg(pgid, signal.SIGKILL)

    def run_task_row(self, task_index, run_counter, start_step_index=0):
        """Executes the steps for a task, logging output directly to files."""
        for i in range(start_step_index, len(self.tasks[task_index]["steps"])):
            step = self.tasks[task_index]["steps"][i]
            with self.state_lock:
                if self.tasks[task_index]['run_counter'] != run_counter:
                    self._log_debug_unsafe(task_index, i, f"Worker with stale run_counter ({run_counter}) exiting.")
                    return
                if step['status'] != STATUS_PENDING:
                    self._log_debug_unsafe(task_index, i, f"Skipping step already in state {step['status']}.")
                    continue
                step["status"] = STATUS_RUNNING; step["start_time"] = time.time()
                self._log_debug_unsafe(task_index, i, f"Starting step (run_counter {run_counter}).")
            try:
                with open(step['log_path'], 'w', encoding='utf-8') as log_file:
                    popen_kwargs = {"shell": True, "stdout": log_file, "stderr": subprocess.STDOUT, "preexec_fn": os.setsid}
                    process = subprocess.Popen(step["command"], **popen_kwargs)
                    with self.state_lock:
                        if self.tasks[task_index]['run_counter'] != run_counter: self._kill_process_group(task_index, i, process); return
                        step["process"] = process
                        self._log_debug_unsafe(task_index, i, f"Process started with PID: {process.pid}. Log: {step['log_path']}")
                    process.wait()
                
                # We need to read back the log to check if it's empty for our success criteria.
                stderr_content = ""
                with open(step['log_path'], 'r', encoding='utf-8') as log_file:
                    full_log = log_file.read()
                    # A more complex script could prefix stderr with "ERROR:" to allow reliable separation.
                    # For now, we revert to the most reliable standard: the exit code.
                    # You can re-add `and not full_log.strip()` to the success condition if needed.
                with self.state_lock:
                    if self.tasks[task_index]['run_counter'] != run_counter: return
                    duration = time.time() - step["start_time"] if step.get("start_time") else 0
                    step["start_time"] = None
                    if step["status"] == STATUS_RUNNING:
                        step["status"] = STATUS_SUCCESS if process.returncode == 0 else STATUS_FAILED
                    self._log_debug_unsafe(task_index, i, f"Process finished code {process.returncode}. Status: {step['status']}. Duration: {duration:.2f}s.")
                    if step["status"] != STATUS_SUCCESS:
                        for j in range(i + 1, len(self.tasks[task_index]["steps"])): self.tasks[task_index]["steps"][j]["status"] = STATUS_SKIPPED
                        break
            except Exception as e:
                with self.state_lock:
                    if self.tasks[task_index]['run_counter'] != run_counter: return
                    step["status"] = STATUS_FAILED; step["start_time"] = None
                    self._log_debug_unsafe(task_index, i, f"CRITICAL ERROR: {e}")
                    try:
                        with open(step['log_path'], 'a', encoding='utf-8') as log_file:
                            log_file.write(f"\n\n--- TASKPANEL CRITICAL ERROR ---\n{e}\n")
                    except IOError: pass
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
                if step_to_reset["status"] == STATUS_RUNNING: step_to_reset["status"] = STATUS_KILLED
                step_to_reset["status"] = STATUS_PENDING; step_to_reset["start_time"] = None
                # Clean up old log file for a fresh start
                try:
                    if os.path.exists(step_to_reset['log_path']):
                        os.remove(step_to_reset['log_path'])
                        self._log_debug_unsafe(task_index, i, f"Removed old log file: {step_to_reset['log_path']}")
                except OSError as e:
                     self._log_debug_unsafe(task_index, i, f"Error removing log file: {e}")
        executor.submit(self.run_task_row, task_index, new_run_counter, start_step_index)

    def kill_task_row(self, task_index):
        with self.state_lock:
            task = self.tasks[task_index]
            self._log_debug_unsafe(task_index, 0, "KILL TASK triggered.")
            task['run_counter'] += 1
            kill_point_found = False
            for i, step in enumerate(task["steps"]):
                if step["status"] == STATUS_RUNNING:
                    if step["process"]: self._kill_process_group(task_index, i, step["process"])
                    step["status"] = STATUS_KILLED
                    if step.get("start_time"): self._log_debug_unsafe(task_index, i, f"KILLED after {time.time() - step['start_time']:.2f}s.")
                    step["start_time"] = None
                    kill_point_found = True
                elif step["status"] == STATUS_PENDING and kill_point_found: step["status"] = STATUS_SKIPPED

    def cleanup(self):
        with self.state_lock:
            for task_index, task in enumerate(self.tasks):
                task['run_counter'] += 1
                for step_index, step in enumerate(task["steps"]):
                    if step["process"]: self._kill_process_group(task_index, step_index, step["process"])
        self.persist_state()