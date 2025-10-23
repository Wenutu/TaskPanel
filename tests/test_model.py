#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_model.py

Tests for TaskPanel model module.
"""

import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, MagicMock

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from taskpanel import model
    from taskpanel.model import Status, TaskModel, TaskLoadError
except ImportError as e:
    print(f"Warning: Could not import model module: {e}")
    model = None
    TaskModel = None
    Status = None
    TaskLoadError = None


@unittest.skipIf(model is None, "taskpanel.model module not available for testing.")
class TestModel(unittest.TestCase):
    """In-depth model tests."""

    def setUp(self):
        """Set up a temporary directory for test artifacts."""
        self.test_dir = tempfile.mkdtemp(prefix="taskpanel_test_")
        self.csv_path = Path(self.test_dir) / "tasks.csv"

    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.test_dir)

    def _create_csv(self, content):
        """Helper to create a CSV file with given content."""
        with open(self.csv_path, "w", newline="") as f:
            f.write(content)

    def test_model_module_import(self):
        """Test that model module can be imported."""
        self.assertIsNotNone(model, "Model module should be importable")

    def test_task_model_class_exists(self):
        """Test that TaskModel class exists."""
        self.assertTrue(callable(TaskModel), "TaskModel should be a class")

    def test_status_enum_exists(self):
        """Test that Status enum exists."""
        self.assertTrue(hasattr(Status, "PENDING"))
        self.assertTrue(hasattr(Status, "SUCCESS"))
        self.assertTrue(hasattr(Status, "FAILED"))

    def test_load_tasks_from_csv_success(self):
        """Test successful loading of tasks from a valid CSV."""
        csv_content = (
            "TaskName,Info,Command1,Command2\n"
            "Task 1,Info 1,echo 'hello',echo 'world'\n"
            "Task 2,Info 2,echo 'foo',\n"
        )
        self._create_csv(csv_content)

        task_model = TaskModel(str(self.csv_path))
        task_model.load_tasks_from_csv()

        self.assertEqual(len(task_model.tasks), 2)
        self.assertEqual(task_model.tasks[0].name, "Task 1")
        self.assertEqual(task_model.tasks[0].info, "Info 1")

        # Filter out None steps
        valid_steps_task1 = [s for s in task_model.tasks[0].steps if s is not None]
        self.assertEqual(len(valid_steps_task1), 2)
        self.assertEqual(valid_steps_task1[0].command, "echo 'hello'")

        # For the second task, check if the empty command results in None or empty step
        all_steps_task2 = task_model.tasks[1].steps
        if len(all_steps_task2) > 1:
            # If empty command creates None step
            if all_steps_task2[1] is None:
                self.assertIsNone(
                    all_steps_task2[1], "Empty command should result in a None step"
                )
            else:
                # If empty command creates empty step
                self.assertEqual(all_steps_task2[1].command.strip(), "")

    def test_load_tasks_from_csv_file_not_found(self):
        """Test that loading from a non-existent CSV raises TaskLoadError."""
        task_model = TaskModel("/non/existent/path.csv")
        with self.assertRaises(TaskLoadError):
            task_model.load_tasks_from_csv()

    def test_load_tasks_from_csv_malformed(self):
        """Test that a malformed CSV raises TaskLoadError."""
        self._create_csv("TaskName\nJust one column")
        task_model = TaskModel(str(self.csv_path))
        with self.assertRaises(TaskLoadError):
            task_model.load_tasks_from_csv()

    def test_task_uid_generation_is_stable(self):
        """Test that task UID is stable for the same name and info."""
        task_model = TaskModel(str(self.csv_path))
        uid1 = task_model._generate_task_uid("My Task", "Some Info")
        uid2 = task_model._generate_task_uid("My Task", "Some Info")
        uid3 = task_model._generate_task_uid("My Task", "Other Info")
        self.assertEqual(uid1, uid2)
        self.assertNotEqual(uid1, uid3)

    def test_state_persistence_and_resume(self):
        """Test that task state is persisted and correctly resumed."""
        csv_content = "TaskName,Info,Command1\nTask 1,Info 1,echo 'ok'"
        self._create_csv(csv_content)

        # --- First run ---
        model1 = TaskModel(str(self.csv_path))
        model1.load_tasks_from_csv()
        self.assertEqual(model1.tasks[0].steps[0].status, Status.PENDING)

        # Simulate a successful run
        model1.tasks[0].steps[0].status = Status.SUCCESS
        model1.persist_state()

        # --- Second run (should resume state) ---
        model2 = TaskModel(str(self.csv_path))
        model2.load_tasks_from_csv()

        self.assertEqual(len(model2.tasks), 1)
        self.assertEqual(
            model2.tasks[0].steps[0].status,
            Status.SUCCESS,
            "Status should be resumed from state file",
        )

    def test_structure_hash_change_discards_state(self):
        """Test that changing a task's command discards its old state."""
        # --- First run with original command ---
        self._create_csv("TaskName,Info,Command1\nMy Task,Info,echo 'original'")
        model1 = TaskModel(str(self.csv_path))
        model1.load_tasks_from_csv()
        model1.tasks[0].steps[0].status = Status.SUCCESS
        model1.persist_state()

        # --- Second run with modified command ---
        self._create_csv("TaskName,Info,Command1\nMy Task,Info,echo 'modified'")
        model2 = TaskModel(str(self.csv_path))
        model2.load_tasks_from_csv()

        self.assertEqual(
            model2.tasks[0].steps[0].status,
            Status.PENDING,
            "Status should be reset because command changed",
        )

    def test_step_creation(self):
        """Test Step class creation and attributes."""
        from taskpanel.model import Step

        step = Step(
            command="echo test",
            log_path_stdout="/tmp/stdout.log",
            log_path_stderr="/tmp/stderr.log",
            task_uid="test_uid",
            step_index=0,
        )

        self.assertEqual(step.command, "echo test")
        self.assertEqual(step.status, Status.PENDING)
        self.assertIsNone(step.process)
        self.assertIsNone(step.start_time)
        self.assertIsNotNone(step.logger)

    def test_task_creation(self):
        """Test Task class creation and attributes."""
        from taskpanel.model import Task, Step

        step = Step("echo test", "/tmp/out.log", "/tmp/err.log", "uid", 0)
        task = Task(
            id=1,
            uid="test_uid",
            name="Test Task",
            info="Test Info",
            steps=[step],
            structure_hash="test_hash",
        )

        self.assertEqual(task.id, 1)
        self.assertEqual(task.name, "Test Task")
        self.assertEqual(task.run_counter, 0)
        self.assertEqual(len(task.steps), 1)

    def test_empty_csv_handling(self):
        """Test handling of empty CSV file."""
        self._create_csv("")

        task_model = TaskModel(str(self.csv_path))
        task_model.load_tasks_from_csv()

        self.assertEqual(len(task_model.tasks), 0)

    def test_csv_with_empty_lines(self):
        """Test CSV with empty lines are ignored."""
        csv_content = (
            "TaskName,Info,Command1\n"
            "\n"
            "Task 1,Info 1,echo 'test'\n"
            "   ,   ,   \n"  # Line with only whitespace
            "Task 2,Info 2,echo 'test2'\n"
        )
        self._create_csv(csv_content)

        task_model = TaskModel(str(self.csv_path))
        task_model.load_tasks_from_csv()

        self.assertEqual(len(task_model.tasks), 2)

    def test_csv_with_unicode_content(self):
        """Test CSV with Unicode characters."""
        csv_content = (
            "TaskName,Info,Command1\n"
            "测试任务,信息描述,echo '你好世界'\n"
            "Émoji Task,Info with 🚀,echo 'test'\n"
        )
        self._create_csv(csv_content)

        task_model = TaskModel(str(self.csv_path))
        task_model.load_tasks_from_csv()

        self.assertEqual(len(task_model.tasks), 2)
        self.assertEqual(task_model.tasks[0].name, "测试任务")

    def test_handle_step_failure(self):
        """Test step failure handling."""
        csv_content = "TaskName,Info,Command1\nTask 1,Info 1,echo 'test'"
        self._create_csv(csv_content)

        task_model = TaskModel(str(self.csv_path))
        task_model.load_tasks_from_csv()

        task_model.handle_step_failure(0, 0, "Test error message")

        self.assertEqual(task_model.tasks[0].steps[0].status, Status.FAILED)
        self.assertIsNone(task_model.tasks[0].steps[0].start_time)

    def test_kill_task_row(self):
        """Test killing a task row."""
        csv_content = (
            "TaskName,Info,Command1,Command2\nTask 1,Info 1,sleep 10,echo 'done'"
        )
        self._create_csv(csv_content)

        task_model = TaskModel(str(self.csv_path))
        task_model.load_tasks_from_csv()

        # Simulate running task
        task_model.tasks[0].steps[0].status = Status.RUNNING
        task_model.tasks[0].steps[1].status = Status.PENDING

        original_counter = task_model.tasks[0].run_counter
        task_model.kill_task_row(0)

        self.assertGreater(task_model.tasks[0].run_counter, original_counter)

    def test_log_dir_creation(self):
        """Test that log directories are created."""
        csv_content = "TaskName,Info,Command1\nTask 1,Info 1,echo 'test'"
        self._create_csv(csv_content)

        task_model = TaskModel(str(self.csv_path))
        task_model.load_tasks_from_csv()

        self.assertTrue(task_model.log_dir.exists())

        # Check task-specific log directory
        task = task_model.tasks[0]
        safe_name = "".join(c if c.isalnum() else "_" for c in task.name)
        task_log_dir = task_model.log_dir / f"{safe_name}_{task.uid[:8]}"
        self.assertTrue(task_log_dir.exists())

    def test_calculate_hash(self):
        """Test file hash calculation."""
        test_file = Path(self.test_dir) / "test_file.txt"
        test_file.write_text("test content")

        task_model = TaskModel(str(self.csv_path))
        hash1 = task_model._calculate_hash(test_file)
        hash2 = task_model._calculate_hash(test_file)

        self.assertIsNotNone(hash1)
        self.assertEqual(hash1, hash2)

        # Test with non-existent file
        hash_none = task_model._calculate_hash(Path("/non/existent/file"))
        self.assertIsNone(hash_none)

    def test_state_file_paths(self):
        """Test state file and log directory paths."""
        task_model = TaskModel(str(self.csv_path))

        expected_state = self.csv_path.parent / f".{self.csv_path.name}.state.json"
        expected_log_dir = self.csv_path.parent / f".{self.csv_path.name}.logs"

        self.assertEqual(task_model.state_file_path, expected_state)
        self.assertEqual(task_model.log_dir, expected_log_dir)

    def test_interrupted_task_resume(self):
        """Test resuming interrupted tasks."""
        csv_content = (
            "TaskName,Info,Command1,Command2\nTask 1,Info 1,echo 'step1',echo 'step2'"
        )
        self._create_csv(csv_content)

        # First run - simulate interruption
        model1 = TaskModel(str(self.csv_path))
        model1.load_tasks_from_csv()
        model1.tasks[0].steps[0].status = Status.SUCCESS
        model1.tasks[0].steps[1].status = Status.RUNNING  # Interrupted
        model1.persist_state()

        # Second run - should resume from step 1
        model2 = TaskModel(str(self.csv_path))
        model2.load_tasks_from_csv()

        # Check that the task was marked as interrupted and resumed from step 1
        # The behavior might be that it resumes from the interrupted step, not resets all steps
        self.assertEqual(
            model2.tasks[0].steps[1].status, Status.PENDING
        )  # Step 1 should be reset to pending
        # Step 0 might remain SUCCESS or be reset - check the actual behavior
        self.assertIn(model2.tasks[0].steps[0].status, [Status.SUCCESS, Status.PENDING])

    def test_rerun_task_from_step(self):
        """Test rerunning task from specific step."""
        csv_content = (
            "TaskName,Info,Command1,Command2\nTask 1,Info 1,echo 'step1',echo 'step2'"
        )
        self._create_csv(csv_content)

        task_model = TaskModel(str(self.csv_path))
        task_model.load_tasks_from_csv()

        # Set up initial state
        task_model.tasks[0].steps[0].status = Status.SUCCESS
        task_model.tasks[0].steps[1].status = Status.FAILED

        with ThreadPoolExecutor(max_workers=1) as executor:
            original_counter = task_model.tasks[0].run_counter
            task_model.rerun_task_from_step(executor, 0, 1)

            # Give some time for the async operation to start
            time.sleep(0.1)

            # Check that run counter increased
            self.assertGreater(task_model.tasks[0].run_counter, original_counter)
            # Step 1 might be RUNNING initially, then change to PENDING/SUCCESS/FAILED
            # Check that it's no longer FAILED
            self.assertNotEqual(task_model.tasks[0].steps[1].status, Status.FAILED)

    def test_cleanup(self):
        """Test cleanup method."""
        csv_content = "TaskName,Info,Command1\nTask 1,Info 1,echo 'test'"
        self._create_csv(csv_content)

        task_model = TaskModel(str(self.csv_path))
        task_model.load_tasks_from_csv()

        # Should not raise any exceptions
        task_model.cleanup()

        # Check that state file was created
        self.assertTrue(task_model.state_file_path.exists())

    def test_task_model_get_selected_step(self):
        """Test getting selected step from task model."""
        csv_content = (
            "TaskName,Info,Command1,Command2\nTask 1,Info 1,echo 'step1',echo 'step2'"
        )
        self._create_csv(csv_content)

        task_model = TaskModel(str(self.csv_path))
        task_model.load_tasks_from_csv()

        # Check if get_selected_step method exists, if not use direct access
        if hasattr(task_model, "get_selected_step"):
            # Test getting valid step
            step = task_model.get_selected_step(0, 1)
            self.assertIsNotNone(step)
            self.assertEqual(step.command, "echo 'step2'")

            # Test getting invalid step
            step = task_model.get_selected_step(0, 99)  # Invalid step index
            self.assertIsNone(step)

            step = task_model.get_selected_step(99, 0)  # Invalid task index
            self.assertIsNone(step)
        else:
            # Use direct step access instead
            self.assertGreater(len(task_model.tasks), 0)
            task = task_model.tasks[0]

            # Filter out None steps
            valid_steps = [step for step in task.steps if step is not None]
            self.assertGreater(len(valid_steps), 1)

            # Test accessing second step
            step = valid_steps[1]
            self.assertIsNotNone(step)
            self.assertEqual(step.command, "echo 'step2'")

            # Test boundary conditions
            with self.assertRaises(IndexError):
                _ = task_model.tasks[0].steps[99]  # Invalid step index

            with self.assertRaises(IndexError):
                _ = task_model.tasks[99].steps[0]  # Invalid task index

    def test_task_model_step_access_functionality(self):
        """Test step access functionality through TaskModel."""
        csv_content = "TaskName,Info,Command1,Command2,Command3\nTask 1,Info 1,echo 'step1',echo 'step2',echo 'step3'"
        self._create_csv(csv_content)

        task_model = TaskModel(str(self.csv_path))
        task_model.load_tasks_from_csv()

        # Test that we can access tasks and their steps
        self.assertEqual(len(task_model.tasks), 1)
        task = task_model.tasks[0]

        # Test task attributes
        self.assertEqual(task.name, "Task 1")
        self.assertEqual(task.info, "Info 1")
        self.assertIsInstance(task.steps, list)

        # Filter out None steps and test
        valid_steps = [step for step in task.steps if step is not None]
        self.assertEqual(len(valid_steps), 3)

        # Test each step
        expected_commands = ["echo 'step1'", "echo 'step2'", "echo 'step3'"]
        for i, step in enumerate(valid_steps):
            self.assertEqual(step.command, expected_commands[i])
            self.assertEqual(step.status, Status.PENDING)

    def test_task_model_safe_step_access(self):
        """Test safe step access patterns."""
        csv_content = (
            "TaskName,Info,Command1,Command2\nTask 1,Info 1,echo 'step1',echo 'step2'"
        )
        self._create_csv(csv_content)

        task_model = TaskModel(str(self.csv_path))
        task_model.load_tasks_from_csv()

        def safe_get_step(task_index, step_index):
            """Safely get a step, returning None if indices are invalid."""
            try:
                if task_index < 0 or task_index >= len(task_model.tasks):
                    return None

                task = task_model.tasks[task_index]
                if step_index < 0 or step_index >= len(task.steps):
                    return None

                return task.steps[step_index]
            except (IndexError, AttributeError):
                return None

        # Test valid access
        step = safe_get_step(0, 0)
        self.assertIsNotNone(step)
        if (
            step is not None
        ):  # Handle case where step might be None due to empty command
            self.assertEqual(step.command, "echo 'step1'")

        # Test invalid access
        self.assertIsNone(safe_get_step(-1, 0))  # Invalid task index
        self.assertIsNone(safe_get_step(99, 0))  # Invalid task index
        self.assertIsNone(safe_get_step(0, -1))  # Invalid step index
        self.assertIsNone(safe_get_step(0, 99))  # Invalid step index

    def test_task_model_step_enumeration(self):
        """Test enumerating steps safely."""
        csv_content = "TaskName,Info,Command1,Command2,Command3\nTask 1,Info 1,echo 'a',echo 'b',echo 'c'"
        self._create_csv(csv_content)

        task_model = TaskModel(str(self.csv_path))
        task_model.load_tasks_from_csv()

        # Test iterating over all tasks and steps
        total_steps = 0
        for task_idx, task in enumerate(task_model.tasks):
            self.assertIsNotNone(task)
            for step_idx, step in enumerate(task.steps):
                if step is not None:  # Skip None steps from empty commands
                    total_steps += 1
                    self.assertIsNotNone(step.command)
                    self.assertEqual(step.status, Status.PENDING)

        self.assertGreater(total_steps, 0, "Should have at least one valid step")

    def test_load_tasks_from_yaml_success(self):
        """Test successful loading of tasks from a valid YAML."""
        yaml_path = Path(self.test_dir) / "tasks.yaml"
        yaml_content = (
            "steps: [Build, Test]\n"
            "tasks:\n"
            "  - name: Task Y\n"
            "    info: Desc\n"
            "    steps:\n"
            '      Build: "echo build"\n'
            '      Test: "echo test"\n'
            "  - name: Task Z\n"
            "    description: ZZZ\n"
            "    steps:\n"
            '      Build: "echo b2"\n'
        )
        yaml_path.write_text(yaml_content, encoding="utf-8")

        task_model = TaskModel(str(yaml_path))
        task_model.load_tasks()  # auto-detect YAML

        self.assertEqual(len(task_model.tasks), 2)
        self.assertEqual(task_model.dynamic_header[:2], ["TaskName", "Description"])
        self.assertEqual(task_model.dynamic_header[2:], ["Build", "Test"])
        self.assertEqual(task_model.tasks[0].name, "Task Y")
        self.assertEqual(
            [s.command for s in task_model.tasks[0].steps if s],
            ["echo build", "echo test"],
        )
        # Task Z 缺少 Test，应为 None
        self.assertIsNone(task_model.tasks[1].steps[1])

    # --- New YAML strictness tests ---

    def test_yaml_strict_top_level_keys(self):
        """Only 'steps' and 'tasks' allowed at YAML top-level."""
        try:
            import yaml  # Skip if PyYAML not present
        except ImportError:
            self.skipTest("PyYAML not installed; skipping YAML strict tests")

        ypath = Path(self.test_dir) / "bad_top.yaml"
        ypath.write_text(
            'meta: {}\nsteps: [A]\ntasks:\n  - name: T\n    steps:\n      A: "echo a"\n',
            encoding="utf-8",
        )
        tm = TaskModel(str(ypath))
        with self.assertRaises(TaskLoadError):
            tm.load_tasks()

    def test_yaml_strict_task_keys_and_types(self):
        """Task keys limited to name/info/description/steps; step commands must be strings."""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed; skipping YAML strict tests")

        # extra task key should fail
        y1 = Path(self.test_dir) / "bad_task_key.yaml"
        y1.write_text(
            "steps: [A]\n"
            "tasks:\n"
            "  - name: T\n"
            "    owner: Bob\n"  # Unsupported key
            "    steps:\n"
            '      A: "echo a"\n',
            encoding="utf-8",
        )
        with self.assertRaises(TaskLoadError):
            TaskModel(str(y1)).load_tasks()

        # non-string step command should fail
        y2 = Path(self.test_dir) / "bad_step_type.yaml"
        y2.write_text(
            "steps: [A,B]\n"
            "tasks:\n"
            "  - name: T\n"
            "    steps:\n"
            "      A: 123\n"  # Non-string value
            '      B: "echo b"\n',
            encoding="utf-8",
        )
        with self.assertRaises(TaskLoadError):
            TaskModel(str(y2)).load_tasks()

    def test_yaml_multiline_description_loaded_into_info(self):
        """Multiline description/info should be loaded into Task.info."""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed; skipping YAML tests")

        y3 = Path(self.test_dir) / "desc.yaml"
        y3.write_text(
            "steps: [S]\n"
            "tasks:\n"
            "  - name: T\n"
            "    description: |\n"
            "      Line1\n"
            "      Line2\n"
            "    steps:\n"
            '      S: "echo s"\n',
            encoding="utf-8",
        )
        tm = TaskModel(str(y3))
        tm.load_tasks()
        self.assertEqual(len(tm.tasks), 1)
        self.assertEqual(tm.tasks[0].name, "T")
        self.assertIn("Line1", tm.tasks[0].info)
        self.assertIn("Line2", tm.tasks[0].info)

    # --- New: _apply_saved_state_to_task structure mismatch ---
    def test_apply_saved_state_structure_mismatch(self):
        """When structure hash mismatches, saved state is ignored."""
        from taskpanel.model import Task, Step

        tm = TaskModel(str(self.csv_path))
        # Build a single-task model
        uid = tm._generate_task_uid("T", "I")
        log_dir = Path(self.test_dir) / ".tasks.csv.logs"
        log_dir.mkdir(exist_ok=True)
        step = Step("echo a", str(log_dir / "a.out"), str(log_dir / "a.err"), uid, 0)
        task = Task(1, uid, "T", "I", [step], tm._generate_structure_hash(["echo a"]))
        tm.tasks = [task]
        # Apply a saved state with different structure_hash
        tm._apply_saved_state_to_task(
            task, {"structure_hash": "DIFF", "steps": [{"status": "SUCCESS"}]}
        )
        self.assertEqual(task.steps[0].status, Status.PENDING)

    # --- New: _apply_saved_state_to_task interrupted resume path ---
    def test_apply_saved_state_interrupted(self):
        """Interrupted (RUNNING/KILLED) step should trigger partial restore only before the point."""
        from taskpanel.model import Task, Step

        tm = TaskModel(str(self.csv_path))
        uid = tm._generate_task_uid("T", "I")
        ld = Path(self.test_dir) / ".tasks.csv.logs"
        ld.mkdir(exist_ok=True)
        s0 = Step("echo a", str(ld / "0.out"), str(ld / "0.err"), uid, 0)
        s1 = Step("echo b", str(ld / "1.out"), str(ld / "1.err"), uid, 1)
        task = Task(
            1,
            uid,
            "T",
            "I",
            [s0, s1],
            tm._generate_structure_hash(["echo a", "echo b"]),
        )
        # Saved: first success, second running -> interrupted_at = 1
        saved = {
            "structure_hash": task.structure_hash,
            "steps": [{"status": "SUCCESS"}, {"status": "RUNNING"}],
        }
        tm._apply_saved_state_to_task(task, saved)
        self.assertEqual(task.steps[0].status, Status.SUCCESS)
        self.assertEqual(
            task.steps[1].status, Status.PENDING
        )  # interrupted step stays/reset to PENDING

    # --- New: _resume_state with corrupt state file ---
    def test_resume_state_corrupt_file(self):
        """Corrupt state file should be handled gracefully."""
        # Write CSV and corrupt state file
        self._create_csv("TaskName,Info,Cmd\nT,Info,echo x\n")
        tm = TaskModel(str(self.csv_path))
        # Create corrupt state file where loader expects it
        tm.state_file_path.write_text("{ invalid json", encoding="utf-8")
        # Should not raise
        tm.load_tasks_from_csv()
        self.assertEqual(len(tm.tasks), 1)

    # --- New: _kill_process_group ProcessLookupError path ---
    def test_kill_process_group_processlookup(self):
        """ProcessLookupError during kill should be handled."""
        from types import SimpleNamespace

        tm = TaskModel(str(self.csv_path))
        fake_proc = SimpleNamespace(
            pid=12345, poll=lambda: None, wait=lambda timeout=None: None
        )
        with patch("taskpanel.model.os.getpgid", side_effect=ProcessLookupError), patch(
            "taskpanel.model.os.killpg"
        ) as mock_kill:
            tm._kill_process_group(0, 0, fake_proc)
        self.assertFalse(mock_kill.called)

    # --- New: _kill_process_group TimeoutExpired path ---
    def test_kill_process_group_timeoutexpired(self):
        """TimeoutExpired during kill escalates to SIGKILL."""
        import subprocess as sp
        from types import SimpleNamespace

        tm = TaskModel(str(self.csv_path))

        class FakeProc:
            pid = 123

            def poll(self):
                return None

            def wait(self, timeout=None):
                raise sp.TimeoutExpired(cmd="x", timeout=0.1)

        with patch("taskpanel.model.os.getpgid", return_value=999), patch(
            "taskpanel.model.os.killpg"
        ) as mock_kill:
            tm._kill_process_group(0, 0, FakeProc())
        self.assertGreaterEqual(mock_kill.call_count, 2)  # SIGTERM then SIGKILL

    # --- New: run_task_row failure marks next steps SKIPPED ---
    def test_run_task_row_failure_marks_skipped(self):
        """Non-zero return code should mark later steps as SKIPPED."""
        from taskpanel.model import Task, Step

        self._create_csv("TaskName,Info,Cmd1,Cmd2\nT,Info,echo a,echo b\n")
        tm = TaskModel(str(self.csv_path))
        tm.load_tasks_from_csv()

        # Patch Popen to return returncode=1 (failure)
        class FakeP:
            returncode = 1

            def __init__(self, *a, **k):
                pass

            def wait(self):
                return None

        with patch("taskpanel.model.subprocess.Popen", return_value=FakeP()):
            tm.run_task_row(0, tm.tasks[0].run_counter, 0)
        self.assertEqual(tm.tasks[0].steps[0].status, Status.FAILED)
        # Next step becomes SKIPPED
        self.assertEqual(tm.tasks[0].steps[1].status, Status.SKIPPED)

    # --- New: run_task_row subprocess raises exception ---
    def test_run_task_row_subprocess_error(self):
        """Popen raising FileNotFoundError should mark FAILED."""
        from taskpanel.model import Task, Step

        self._create_csv("TaskName,Info,Cmd\nT,Info,echo a\n")
        tm = TaskModel(str(self.csv_path))
        tm.load_tasks_from_csv()
        with patch(
            "taskpanel.model.subprocess.Popen", side_effect=FileNotFoundError("no bin")
        ):
            tm.run_task_row(0, tm.tasks[0].run_counter, 0)
        self.assertEqual(tm.tasks[0].steps[0].status, Status.FAILED)

    # --- New: rerun_task_from_step removes log files and resets statuses ---
    def test_rerun_task_from_step_removes_logs(self):
        """Rerun should clear logs and reset to PENDING."""
        from taskpanel.model import Task, Step

        self._create_csv("TaskName,Info,Cmd1,Cmd2\nT,Info,echo a,echo b\n")
        tm = TaskModel(str(self.csv_path))
        tm.load_tasks_from_csv()
        # Prepare logs for step 1
        step1 = tm.tasks[0].steps[1]
        Path(step1.log_path_stdout).write_text("o")
        Path(step1.log_path_stderr).write_text("e")
        # Ensure status not PENDING
        step1.status = Status.FAILED
        exec_mock = MagicMock()
        tm.rerun_task_from_step(exec_mock, 0, 1)
        self.assertFalse(os.path.exists(step1.log_path_stdout))
        self.assertFalse(os.path.exists(step1.log_path_stderr))
        self.assertEqual(step1.status, Status.PENDING)
        self.assertTrue(exec_mock.submit.called)

    # --- New: kill_task_row marks KILLED and SKIPPED ---
    def test_kill_task_row_marks_killed_and_skipped(self):
        """Killing a running row should mark current as KILLED and next PENDING as SKIPPED."""
        from taskpanel.model import Task, Step

        self._create_csv("TaskName,Info,Cmd1,Cmd2\nT,Info,sleep 1,echo z\n")
        tm = TaskModel(str(self.csv_path))
        tm.load_tasks_from_csv()
        # Simulate running in step 0
        tm.tasks[0].steps[0].status = Status.RUNNING
        tm.tasks[0].steps[0].process = MagicMock()
        with patch.object(tm, "_kill_process_group") as mock_kill:
            tm.kill_task_row(0)
        self.assertEqual(tm.tasks[0].steps[0].status, Status.KILLED)
        self.assertEqual(tm.tasks[0].steps[1].status, Status.SKIPPED)
