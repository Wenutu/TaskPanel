#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TaskPanel - Model (Python 3.6+ Compatible, Refactored & Optimized)

This module defines the data structures and core business logic for the task runner.
OPTIMIZED with stable log paths, independent of CSV line numbers.
"""
import csv
import hashlib
import json
import logging
import logging.handlers
import os
import signal
import subprocess
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

# --- Constants ---
STATE_FILE_SUFFIX = ".state.json"
LOG_DIR_SUFFIX = ".logs"
DEBUG_LOG_MAX_LINES = 50
PROCESS_KILL_TIMEOUT_S = 2
HASH_CHUNK_SIZE = 8192


# --- Enums and Exceptions ---
class Status(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    KILLED = "KILLED"


class TaskLoadError(Exception):
    pass


# --- Data Structures ---
class Step:
    def __init__(
        self,
        command: str,
        log_path_stdout: str,
        log_path_stderr: str,
        task_uid: str,
        step_index: int,
    ):
        self.command = command
        self.status = Status.PENDING
        self.process: Optional[subprocess.Popen] = None
        self.log_path_stdout = log_path_stdout
        self.log_path_stderr = log_path_stderr
        self.start_time: Optional[float] = None
        self.logger = logging.getLogger(
            f"taskpanel.task.{task_uid[:8]}.step.{step_index}"
        )
        self.logger.propagate = False
        self.logger.setLevel(logging.DEBUG)

        self.log_handler = logging.handlers.MemoryHandler(capacity=DEBUG_LOG_MAX_LINES)
        formatter = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
        self.log_handler.setFormatter(formatter)

        if not self.logger.handlers:
            self.logger.addHandler(self.log_handler)

    def __repr__(self):
        return f"Step(command='{self.command[:30]}...', status={self.status.value})"


class Task:
    def __init__(
        self,
        id: int,
        uid: str,
        name: str,
        info: str,
        steps: List[Optional[Step]],
        structure_hash: str,
    ):
        self.id = id
        self.uid = uid
        self.name = name
        self.info = info
        self.steps = steps
        self.structure_hash = structure_hash
        self.run_counter = 0

    def __repr__(self):
        return f"Task(uid='{self.uid[:8]}...', name='{self.name}', steps={len(self.steps)})"


class TaskModel:
    def __init__(self, csv_path: str):
        self.csv_path = Path(csv_path)
        base_name = self.csv_path.name
        self.state_file_path = self.csv_path.parent / f".{base_name}{STATE_FILE_SUFFIX}"
        self.log_dir = self.csv_path.parent / f".{base_name}{LOG_DIR_SUFFIX}"
        self.tasks: List[Task] = []
        self.dynamic_header: List[str] = []
        self.state_lock = threading.RLock()

    def _generate_task_uid(self, name: str, info: str) -> str:
        salt = "taskpanel-uid-salt"
        h = hashlib.sha256()
        h.update(salt.encode("utf-8"))
        h.update(name.encode("utf-8"))
        h.update(info.encode("utf-8"))
        return h.hexdigest()

    def _generate_structure_hash(self, commands: List[str]) -> str:
        h = hashlib.sha256()
        h.update("|".join(commands).encode("utf-8"))
        return h.hexdigest()

    def _log_step_debug(self, task_index: int, step_index: int, message: str):
        if 0 <= task_index < len(self.tasks) and 0 <= step_index < len(
            self.tasks[task_index].steps
        ):
            step = self.tasks[task_index].steps[step_index]
            if step:
                step.logger.debug(message)

    def _calculate_hash(self, file_path: Path) -> Optional[str]:
        sha256 = hashlib.sha256()
        try:
            with file_path.open("rb") as f:
                for chunk in iter(lambda: f.read(HASH_CHUNK_SIZE), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except IOError:
            return None

    def load_tasks_from_csv(self):
        print(f"Loading tasks from '{self.csv_path}'...")
        try:
            self.log_dir.mkdir(exist_ok=True)
            with self.csv_path.open("r", encoding="utf-8") as f:
                reader = csv.reader(f)
                all_rows = [
                    row for row in reader if row and any(cell.strip() for cell in row)
                ]
                if not all_rows:
                    return
                self.dynamic_header = [h.strip() for h in all_rows.pop(0)]
                if len(self.dynamic_header) < 2:
                    raise TaskLoadError(
                        "FATAL: CSV header must have at least 'TaskName' and 'Info' columns."
                    )
                num_command_cols = max(0, len(self.dynamic_header) - 2)
                for line_num, row in enumerate(all_rows, 2):
                    if len(row) < 2:
                        raise TaskLoadError(
                            f"FATAL: CSV parsing error on line {line_num}. "
                            f"Expected at least 2 columns ('TaskName', 'Info'), but got {len(row)}."
                        )
                    name, info = row[0].strip(), row[1].strip()
                    uid = self._generate_task_uid(name, info)
                    commands = [
                        (row[i + 2].strip() if len(row) > i + 2 else "")
                        for i in range(num_command_cols)
                    ]
                    structure_hash = self._generate_structure_hash(commands)
                    safe_name = "".join(c if c.isalnum() else "_" for c in name)

                    log_path = self.log_dir / f"{safe_name}_{uid[:8]}"

                    log_path.mkdir(exist_ok=True)
                    steps = [
                        (
                            Step(
                                cmd,
                                str(log_path / f"step{i}.stdout.log"),
                                str(log_path / f"step{i}.stderr.log"),
                                uid,
                                i,
                            )
                            if cmd
                            else None
                        )
                        for i, cmd in enumerate(commands)
                    ]
                    self.tasks.append(
                        Task(line_num, uid, name, info, steps, structure_hash)
                    )
            print(f"Loaded {len(self.tasks)} tasks successfully.")
            self._resume_state()
        except (FileNotFoundError, csv.Error, IOError) as e:
            raise TaskLoadError(
                f"FATAL: Could not load tasks from '{self.csv_path}': {e}"
            )

    def _apply_saved_state_to_task(self, task: Task, saved_state: Dict):
        if task.structure_hash != saved_state.get("structure_hash"):
            print(f"  - Task '{task.name}' structure changed. Discarding old state.")
            return
        saved_steps = saved_state.get("steps", [])
        interrupted_at = -1
        for i, s_state in enumerate(saved_steps):
            if (
                i < len(task.steps)
                and task.steps[i]
                and s_state
                and s_state.get("status") in [Status.RUNNING.value, Status.KILLED.value]
            ):
                interrupted_at = i
                break
        if interrupted_at != -1:
            print(
                f"  - Task '{task.name}' was interrupted. Resuming from step {interrupted_at}."
            )
            for i in range(interrupted_at):
                if (
                    i < len(task.steps)
                    and i < len(saved_steps)
                    and task.steps[i]
                    and saved_steps[i]
                ):
                    task.steps[i].status = Status(
                        saved_steps[i].get("status", Status.PENDING.value)
                    )
        else:
            for i, s_state in enumerate(saved_steps):
                if i < len(task.steps) and task.steps[i] and s_state:
                    task.steps[i].status = Status(
                        s_state.get("status", Status.PENDING.value)
                    )

    def _resume_state(self):
        if not self.state_file_path.exists():
            print("No state file found. Starting fresh.")
            return
        print(
            f"Found state file: {self.state_file_path}. Resuming state based on task identity..."
        )
        try:
            with self.state_file_path.open("r") as f:
                saved_data = json.load(f)
            with self.state_lock:
                task_map = {task.uid: task for task in self.tasks}
                saved_states = {
                    s["uid"]: s for s in saved_data.get("tasks", []) if "uid" in s
                }
                for uid, task in task_map.items():
                    if uid in saved_states:
                        self._apply_saved_state_to_task(task, saved_states[uid])
        except (json.JSONDecodeError, IOError, KeyError) as e:
            print(
                f"Warning: Could not parse state file '{self.state_file_path}'. Starting fresh. Error: {e}"
            )

    def persist_state(self):
        print("\nPersisting state...")
        state_to_save = []
        with self.state_lock:
            for task in self.tasks:
                # The loop should iterate over the steps of the current `task` object.
                steps_data = [
                    {"status": s.status.value} if s else None for s in task.steps
                ]
                task_data = {
                    "uid": task.uid,
                    "structure_hash": task.structure_hash,
                    "name": task.name,
                    "steps": steps_data,
                }
                state_to_save.append(task_data)
        final_data = {
            "source_csv_sha256": self._calculate_hash(self.csv_path),
            "tasks": state_to_save,
        }
        temp_file_path = self.state_file_path.with_suffix(
            self.state_file_path.suffix + ".tmp"
        )
        try:
            with temp_file_path.open("w") as f:
                json.dump(final_data, f, indent=2)
            os.rename(str(temp_file_path), str(self.state_file_path))
            print(f"State saved to {self.state_file_path}")
        except (IOError, OSError) as e:
            print(
                f"\nError: Could not write state to file '{self.state_file_path}'. Error: {e}"
            )
            if temp_file_path.exists():
                temp_file_path.unlink()

    def handle_step_failure(self, task_index: int, step_index: int, error_message: str):
        with self.state_lock:
            task = self.tasks[task_index]
            step = task.steps[step_index]
            if task.run_counter != task.run_counter:
                return
            step.status = Status.FAILED
            step.start_time = None
            self._log_step_debug(task_index, step_index, error_message)
            try:
                with open(step.log_path_stderr, "ab") as f:
                    f.write(
                        f"\n--- TASKPANEL CRITICAL ERROR ---\n{error_message}\n".encode()
                    )
            except IOError:
                pass

    def run_task_row(
        self, task_index: int, run_counter: int, start_step_index: int = 0
    ):
        task = self.tasks[task_index]
        for i in range(start_step_index, len(task.steps)):
            step = task.steps[i]
            if not step:
                continue
            with self.state_lock:
                if task.run_counter != run_counter:
                    self._log_step_debug(
                        task_index,
                        i,
                        f"Worker with stale run_counter ({run_counter}) exiting.",
                    )
                    return
                if step.status != Status.PENDING:
                    self._log_step_debug(
                        task_index,
                        i,
                        f"Skipping step already in state {step.status.value}.",
                    )
                    continue
                step.status = Status.RUNNING
                step.start_time = time.time()
                self._log_step_debug(
                    task_index, i, f"Starting step (run_counter {run_counter})."
                )
            try:
                with open(step.log_path_stdout, "wb") as stdout_log, open(
                    step.log_path_stderr, "wb"
                ) as stderr_log:
                    process = subprocess.Popen(
                        step.command,
                        shell=True,
                        stdout=stdout_log,
                        stderr=stderr_log,
                        preexec_fn=os.setsid,
                    )
                    with self.state_lock:
                        if task.run_counter != run_counter:
                            self._kill_process_group(task_index, i, process)
                            return
                        step.process = process
                        self._log_step_debug(
                            task_index, i, f"Process started PID: {process.pid}."
                        )
                    process.wait()
                with self.state_lock:
                    if task.run_counter != run_counter:
                        return
                    duration = time.time() - step.start_time if step.start_time else 0
                    if step.status == Status.RUNNING:
                        step.status = (
                            Status.SUCCESS if process.returncode == 0 else Status.FAILED
                        )
                    self._log_step_debug(
                        task_index,
                        i,
                        f"Process finished code {process.returncode}. Status: {step.status.value}. Duration: {duration:.2f}s.",
                    )
                    if step.status != Status.SUCCESS:
                        for j in range(i + 1, len(task.steps)):
                            if task.steps[j]:
                                task.steps[j].status = Status.SKIPPED
                        break
            except (FileNotFoundError, OSError, subprocess.SubprocessError) as e:
                err_msg = f"CRITICAL ERROR: Failed to execute command. Details: {e}"
                self.handle_step_failure(task_index, i, err_msg)
                break

    def _kill_process_group(
        self, task_index: int, step_index: int, process: subprocess.Popen
    ):
        if process.poll() is None:
            try:
                pgid = os.getpgid(process.pid)
                if process.poll() is not None:
                    return
                with self.state_lock:
                    self._log_step_debug(
                        task_index, step_index, f"Killing process group {pgid}..."
                    )
                os.killpg(pgid, signal.SIGTERM)
                process.wait(timeout=PROCESS_KILL_TIMEOUT_S)
            except (ProcessLookupError, PermissionError):
                with self.state_lock:
                    self._log_step_debug(
                        task_index,
                        step_index,
                        f"PGID for PID {process.pid} already gone.",
                    )
            except subprocess.TimeoutExpired:
                with self.state_lock:
                    self._log_step_debug(
                        task_index, step_index, "PG unresponsive, sending SIGKILL."
                    )
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)

    def rerun_task_from_step(self, executor, task_index: int, start_step_index: int):
        with self.state_lock:
            task = self.tasks[task_index]
            self._log_step_debug(task_index, start_step_index, "RERUN triggered.")
            task.run_counter += 1
            new_run_counter = task.run_counter
            self._log_step_debug(
                task_index, start_step_index, f"New run_counter is {new_run_counter}."
            )

            for i, step in enumerate(task.steps):
                if step and step.process:
                    self._kill_process_group(task_index, i, step.process)

            for i in range(start_step_index, len(task.steps)):
                step = task.steps[i]
                if step:
                    step.status = Status.PENDING
                    step.start_time = None
                    try:
                        if os.path.exists(step.log_path_stdout):
                            os.remove(step.log_path_stdout)
                        if os.path.exists(step.log_path_stderr):
                            os.remove(step.log_path_stderr)
                        self._log_step_debug(
                            task_index, i, f"Removed old log files for step {i}"
                        )
                    except OSError as e:
                        self._log_step_debug(
                            task_index, i, f"Error removing log files: {e}"
                        )
        executor.submit(
            self.run_task_row, task_index, new_run_counter, start_step_index
        )

    def kill_task_row(self, task_index: int):
        with self.state_lock:
            task = self.tasks[task_index]
            self._log_step_debug(task_index, 0, "KILL TASK triggered.")
            task.run_counter += 1
            kill_point_found = False
            for i, step in enumerate(task.steps):
                if step:
                    if step.status == Status.RUNNING:
                        if step.process:
                            self._kill_process_group(task_index, i, step.process)
                        step.status = Status.KILLED
                        if step.start_time:
                            self._log_step_debug(
                                task_index,
                                i,
                                f"KILLED after {time.time() - step.start_time:.2f}s.",
                            )
                        step.start_time = None
                        kill_point_found = True
                    elif step.status == Status.PENDING and kill_point_found:
                        step.status = Status.SKIPPED

    def cleanup(self):
        with self.state_lock:
            print("\nCleaning up running processes...")
            for idx, task in enumerate(self.tasks):
                task.run_counter += 1
                for i, step in enumerate(task.steps):
                    if step and step.process:
                        self._kill_process_group(idx, i, step.process)
        self.persist_state()
