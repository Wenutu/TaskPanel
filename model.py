#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HPC Task Runner - Model (Refined & Hardened)

This file defines the data structures and core business logic for the task runner.
It is completely independent of the UI (View) and user input handling (Controller).
This represents the "Model" in a Model-View-Controller (MVC) architecture.

Key Responsibilities:
- Loading and parsing tasks from a CSV file.
- Managing the state of each task and step (status, output, timings, etc.).
- Executing shell commands in subprocesses using a simple and robust `communicate()` model.
- Handling the logic for killing, rerunning, and cleaning up tasks.
- Persisting state to a file with SHA256 integrity checks and resuming from it robustly.
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
        # State filename is scoped to the input CSV file for project isolation.
        self.state_file_path = f".{os.path.basename(csv_path)}.state.json"
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
                # Python 3.6 compatible way to read in chunks.
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
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                all_rows = [row for row in reader if row and row[0].strip()]
                if not all_rows: raise StopIteration
                longest_row = max(all_rows, key=len)
                self.dynamic_header = ["TaskName", "Info"] + [cmd.strip().split()[0].split('/')[-1] for cmd in longest_row[2:]]
                for row in all_rows:
                    if len(row) < 2: continue # Skip rows that don't even have a name and info
                    task_name = row[0].strip()
                    info = row[1].strip() if len(row) > 1 else ""
                    commands = [cmd for cmd in row[2:] if cmd.strip()]
                    steps = [{"command": cmd, "status": STATUS_PENDING, "process": None,
                              "output": {"stdout": "", "stderr": ""}, "start_time": None,
                              "debug_log": deque(maxlen=50)} for cmd in commands]
                    self.tasks.append({"name": task_name, "info": info, "steps": steps, "run_counter": 0})
            print("Tasks loaded successfully.")
            self._resume_state()
        except Exception as e:
            print(f"FATAL: Error loading tasks from '{self.csv_path}': {e}"); sys.exit(1)

    def _resume_state(self):
        """If a state file exists and matches the CSV hash, load it."""
        if not os.path.exists(self.state_file_path):
            print("No state file found. Starting fresh.")
            return
        print(f"Found state file: {self.state_file_path}. Verifying integrity...")
        try:
            with open(self.state_file_path, 'r') as f: saved_data = json.load(f)
            current_hash = self._calculate_hash(self.csv_path)
            saved_hash = saved_data.get("source_csv_sha256")
            if current_hash != saved_hash:
                print(f"Warning: '{self.csv_path}' has changed since the last run. Discarding old state.")
                os.remove(self.state_file_path)
                return
            print("Integrity check passed. Resuming state.")
            with self.state_lock:
                task_map = {task['name']: task for task in self.tasks}
                for task_state in saved_data.get("tasks", []):
                    task_name = task_state.get('name')
                    if task_name in task_map:
                        task = task_map[task_name]
                        was_interrupted = any(
                            s.get('status') in [STATUS_RUNNING, STATUS_KILLED]
                            for s in task_state.get('steps', [])
                        )

                        if was_interrupted:
                            print(f"  - Task '{task_name}' was interrupted. Resetting to PENDING for re-execution.")
                            for step in task['steps']:
                                step['status'] = STATUS_PENDING
                        else:
                            task['info'] = task_state.get('info', task['info'])
                            for i, saved_step in enumerate(task_state.get('steps', [])):
                                if i < len(task['steps']):
                                    status = saved_step.get('status', STATUS_PENDING)
                                    if status not in [STATUS_RUNNING, STATUS_KILLED]:
                                        task['steps'][i]['status'] = saved_step.get('status', STATUS_PENDING)
                                        task['steps'][i]['output'] = saved_step.get('output', {"stdout": "", "stderr": ""})
                                        task['steps'][i]['debug_log'] = deque(saved_step.get('debug_log', []), maxlen=50)
        except (json.JSONDecodeError, IOError, KeyError) as e:
            print(f"Warning: Could not read or parse state file '{self.state_file_path}'. Starting fresh. Error: {e}")

    def persist_state(self):
        """Saves the current state of all tasks and the CSV hash to a file."""
        print("\nPersisting state...")
        state_to_save = []
        with self.state_lock:
            for task in self.tasks:
                steps_data = []
                for s in task['steps']:
                    steps_data.append({
                        "command": s['command'],
                        "status": s['status'],
                        "output": s['output'],
                        "debug_log": list(s['debug_log']) # Convert deque to list for JSON
                    })
                task_data = {
                    "name": task['name'],
                    "info": task['info'],
                    "steps": steps_data
                }
                state_to_save.append(task_data)
        final_data = {"source_csv_sha256": self._calculate_hash(self.csv_path), "tasks": state_to_save}
        try:
            with open(self.state_file_path, 'w') as f: json.dump(final_data, f, indent=2)
            print(f"State saved to {self.state_file_path}")
        except IOError as e:
            print(f"\nError: Could not write state to file '{self.state_file_path}'. Error: {e}")

    def _kill_process_group(self, task_index, step_index, process):
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
        """A simplified and robust function to execute steps for a task."""
        for i in range(start_step_index, len(self.tasks[task_index]["steps"])):
            step = self.tasks[task_index]["steps"][i]
            with self.state_lock:
                if self.tasks[task_index]['run_counter'] != run_counter:
                    self._log_debug_unsafe(task_index, i, f"Worker with stale run_counter ({run_counter}) exiting.")
                    return
                if i > 0 and self.tasks[task_index]["steps"][i-1]["status"] in [STATUS_FAILED, STATUS_SKIPPED, STATUS_KILLED]:
                    step["status"] = STATUS_SKIPPED; continue
                step["status"] = STATUS_RUNNING; step["start_time"] = time.time()
                self._log_debug_unsafe(task_index, i, f"Starting step (run_counter {run_counter}).")
            try:
                popen_kwargs = {"shell": True, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "preexec_fn": os.setsid}
                if sys.version_info >= (3, 7): popen_kwargs['text'] = True; popen_kwargs['encoding'] = 'utf-8'
                else: popen_kwargs['universal_newlines'] = True
                process = subprocess.Popen(step["command"], **popen_kwargs)
                with self.state_lock:
                    if self.tasks[task_index]['run_counter'] != run_counter: self._kill_process_group(task_index, i, process); return
                    step["process"] = process
                    self._log_debug_unsafe(task_index, i, f"Process started with PID: {process.pid}")
                
                stdout, stderr = process.communicate()
                
                with self.state_lock:
                    if self.tasks[task_index]['run_counter'] != run_counter: return
                    duration = time.time() - step["start_time"] if step.get("start_time") else 0
                    step["start_time"] = None
                    step["output"] = {"stdout": stdout, "stderr": stderr}
                    if step["status"] == STATUS_RUNNING:
                        step["status"] = STATUS_SUCCESS if process.returncode == 0 and not stderr.strip() else STATUS_FAILED
                    self._log_debug_unsafe(task_index, i, f"Process finished code {process.returncode}. Status: {step['status']}. Duration: {duration:.2f}s.")
                    if step["status"] != STATUS_SUCCESS:
                        for j in range(i + 1, len(self.tasks[task_index]["steps"])): self.tasks[task_index]["steps"][j]["status"] = STATUS_SKIPPED
                        break
            except Exception as e:
                with self.state_lock:
                    if self.tasks[task_index]['run_counter'] != run_counter: return
                    step["status"] = STATUS_FAILED; step["start_time"] = None
                    self._log_debug_unsafe(task_index, i, f"CRITICAL ERROR: {e}")
                break

    def rerun_task_from_step(self, executor, task_index, start_step_index):
        with self.state_lock:
            task = self.tasks[task_index]
            self._log_debug_unsafe(task_index, start_step_index, "RERUN triggered.")
            task['run_counter'] += 1
            new_run_counter = task['run_counter']
            self._log_debug_unsafe(task_index, start_step_index, f"New run_counter is {new_run_counter}.")
            for i in range(start_step_index, len(task["steps"])):
                if task["steps"][i]["process"]: self._kill_process_group(task_index, i, task["steps"][i]["process"])
                if task["steps"][i]["status"] == STATUS_RUNNING: task["steps"][i]["status"] = STATUS_KILLED
            for i in range(start_step_index, len(task["steps"])):
                step = task["steps"][i]
                step["status"] = STATUS_PENDING; step["start_time"] = None; step["output"] = {"stdout": "", "stderr": ""}
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