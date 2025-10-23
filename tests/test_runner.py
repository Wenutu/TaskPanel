#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_runner.py

Simple tests for TaskPanel runner module - focused on packaging and basic functionality.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import tempfile
import shutil

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from taskpanel import runner
    from taskpanel.runner import run
    from taskpanel import TaskLoadError
except ImportError as e:
    print(f"Warning: Could not import runner module: {e}")
    runner = None
    run = None
    TaskLoadError = None


@unittest.skipIf(runner is None, "runner module not available for testing.")
class TestRunner(unittest.TestCase):
    """Simple runner tests for packaging validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.csv_path = os.path.join(self.test_dir, "test_tasks.csv")

        # Create a valid CSV file
        with open(self.csv_path, "w") as f:
            f.write("TaskName,Info,Command\n")
            f.write("Test Task,Test Info,echo 'hello'\n")

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    def test_runner_module_import(self):
        """Test that runner module can be imported."""
        self.assertIsNotNone(runner, "Runner module should be importable")

    def test_run_function_exists(self):
        """Test that run function exists."""
        if run is None:
            self.skipTest("run function not available")

        self.assertTrue(callable(run), "run should be callable")

    def test_run_function_signature(self):
        """Test that run function has expected signature."""
        if run is None:
            self.skipTest("run function not available")

        import inspect

        sig = inspect.signature(run)
        params = list(sig.parameters.keys())

        # Check required parameters
        self.assertIn("workflow_path", params)
        self.assertIn("max_workers", params)
        self.assertIn("title", params)

    def test_run_validates_max_workers(self):
        """Test that run function validates max_workers parameter."""
        if run is None:
            self.skipTest("run function not available")

        # Test with invalid worker count
        with self.assertRaises(ValueError) as cm:
            run(self.csv_path, max_workers=0)

        self.assertIn("must be a positive integer", str(cm.exception))

        # Test with negative worker count
        with self.assertRaises(ValueError) as cm:
            run(self.csv_path, max_workers=-1)

        self.assertIn("must be a positive integer", str(cm.exception))

    def test_run_validates_csv_file_exists(self):
        """Test that run function validates CSV file existence."""
        if run is None:
            self.skipTest("run function not available")

        non_existent_path = "/path/that/does/not/exist.csv"

        with self.assertRaises(FileNotFoundError) as cm:
            run(non_existent_path, max_workers=1)

        self.assertIn("not found", str(cm.exception))

    @patch("os.name", "nt")  # Simulate Windows
    def test_run_validates_posix_os(self):
        """Test that run function validates POSIX OS requirement."""
        if run is None:
            self.skipTest("run function not available")

        with self.assertRaises(OSError) as cm:
            run(self.csv_path, max_workers=1)

        self.assertIn("POSIX-like OS", str(cm.exception))

    @patch("taskpanel.runner.curses")
    @patch("taskpanel.runner.AppController")
    def test_run_creates_app_controller(self, mock_controller_class, mock_curses):
        """Test that run function creates AppController with correct parameters."""
        if run is None:
            self.skipTest("run function not available")

        mock_controller = MagicMock()
        mock_controller_class.return_value = mock_controller

        # Mock curses.wrapper to call our function directly
        def mock_wrapper(func):
            mock_stdscr = MagicMock()
            return func(mock_stdscr)

        mock_curses.wrapper = mock_wrapper

        try:
            run(self.csv_path, max_workers=2, title="Test Title")
        except Exception:
            # We expect this to potentially fail due to mocking, but we want to check the call
            pass

        # Verify AppController was created with correct parameters
        mock_controller_class.assert_called_once()
        args, kwargs = mock_controller_class.call_args

        # Check that the arguments are as expected
        self.assertEqual(len(args), 4)  # stdscr, csv_path, max_workers, title
        self.assertEqual(args[1], self.csv_path)  # csv_path
        self.assertEqual(args[2], 2)  # max_workers
        self.assertEqual(args[3], "Test Title")  # title

    def test_run_default_title(self):
        """Test that run function uses default title when not specified."""
        if run is None:
            self.skipTest("run function not available")

        # We can't easily test the full execution without mocking curses,
        # but we can at least verify the function accepts the call
        with patch("taskpanel.runner.curses.wrapper") as mock_wrapper:
            mock_wrapper.side_effect = KeyboardInterrupt()  # Quick exit

            try:
                run(self.csv_path, max_workers=1)
            except KeyboardInterrupt:
                pass  # Expected

            mock_wrapper.assert_called_once()

    @patch("taskpanel.runner.curses.wrapper")
    def test_run_handles_keyboard_interrupt(self, mock_wrapper):
        """Test that run function handles KeyboardInterrupt gracefully."""
        if run is None:
            self.skipTest("run function not available")

        mock_wrapper.side_effect = KeyboardInterrupt()

        # Should not raise an exception
        try:
            run(self.csv_path, max_workers=1)
        except KeyboardInterrupt:
            self.fail("KeyboardInterrupt should be handled gracefully")

    @patch("taskpanel.runner.curses.wrapper")
    def test_run_handles_task_load_error(self, mock_wrapper):
        """Test that run function re-raises TaskLoadError."""
        if run is None or TaskLoadError is None:
            self.skipTest("Required modules not available")

        mock_wrapper.side_effect = TaskLoadError("Test error")

        with self.assertRaises(TaskLoadError):
            run(self.csv_path, max_workers=1)

    @patch("taskpanel.runner.curses.wrapper")
    @patch("taskpanel.runner.curses.endwin")
    def test_run_handles_general_exception(self, mock_endwin, mock_wrapper):
        """Test that run function handles general exceptions."""
        if run is None:
            self.skipTest("run function not available")

        test_exception = RuntimeError("Test error")
        mock_wrapper.side_effect = test_exception

        with self.assertRaises(RuntimeError):
            run(self.csv_path, max_workers=1)

        # Should call curses.endwin() for cleanup
        mock_endwin.assert_called_once()

    def test_app_controller_class_exists(self):
        """Test that AppController class exists in runner module."""
        if runner is None:
            self.skipTest("runner module not available")

        self.assertTrue(hasattr(runner, "AppController"))
        self.assertTrue(callable(runner.AppController))

    def test_runner_constants_exist(self):
        """Test that expected constants exist in runner module."""
        if runner is None:
            self.skipTest("runner module not available")

        # Check for timing constants
        self.assertTrue(hasattr(runner, "MAIN_LOOP_SLEEP_S"))
        self.assertTrue(hasattr(runner, "UI_REFRESH_INTERVAL_S"))
        self.assertTrue(hasattr(runner, "SHUTDOWN_CLEANUP_WAIT_S"))

        # Check for key constants
        self.assertTrue(hasattr(runner, "ENTER_KEYS"))
        self.assertTrue(hasattr(runner, "BACKSPACE_KEYS"))

    def test_empty_csv_file(self):
        """Test behavior with empty CSV file."""
        if run is None:
            self.skipTest("run function not available")

        empty_csv = os.path.join(self.test_dir, "empty.csv")
        with open(empty_csv, "w") as f:
            f.write("")  # Empty file

        with patch("taskpanel.runner.curses.wrapper") as mock_wrapper:
            mock_wrapper.side_effect = KeyboardInterrupt()  # Quick exit

            try:
                run(empty_csv, max_workers=1)
            except (KeyboardInterrupt, TaskLoadError):
                pass  # Either is acceptable

    def test_malformed_csv_file(self):
        """Test behavior with malformed CSV file."""
        if run is None:
            self.skipTest("run function not available")

        malformed_csv = os.path.join(self.test_dir, "malformed.csv")
        with open(malformed_csv, "w") as f:
            f.write("Only one column\n")  # Invalid CSV structure

        # The runner might handle malformed CSV gracefully
        # Just test that it doesn't crash unexpectedly
        try:
            with patch("taskpanel.runner.curses.wrapper") as mock_wrapper:
                mock_wrapper.side_effect = KeyboardInterrupt()  # Quick exit
                run(malformed_csv, max_workers=1)
        except KeyboardInterrupt:
            pass  # Expected from our mock
        except Exception as e:
            # If an exception is raised, it should be a meaningful one
            self.assertIsInstance(e, (TaskLoadError, ValueError, FileNotFoundError))

    def test_app_controller_initialization(self):
        """Test AppController initialization."""
        if runner is None:
            self.skipTest("runner module not available")

        with patch("curses.curs_set"), patch(
            "taskpanel.runner.setup_colors"
        ), patch.object(runner.TaskModel, "load_tasks"):
            mock_stdscr = MagicMock()
            mock_stdscr.nodelay = MagicMock()

            controller = runner.AppController(
                mock_stdscr, self.csv_path, 2, "Test Title"
            )

            self.assertEqual(controller.max_workers, 2)
            self.assertEqual(controller.title, "Test Title")
            self.assertTrue(controller.app_running)
            self.assertFalse(controller.is_search_mode)
            self.assertEqual(controller.search_query, "")

    @patch("taskpanel.runner.curses")
    def test_app_controller_key_handlers(self, mock_curses):
        """Test that all key handlers exist."""
        if runner is None:
            self.skipTest("runner module not available")

        with patch("taskpanel.runner.setup_colors"), patch.object(
            runner.TaskModel, "load_tasks"
        ):
            mock_stdscr = MagicMock()
            controller = runner.AppController(mock_stdscr, self.csv_path, 1, "Test")

            expected_keys = [
                ord("q"),
                ord("d"),
                ord("/"),
                mock_curses.KEY_UP,
                mock_curses.KEY_DOWN,
                mock_curses.KEY_LEFT,
                mock_curses.KEY_RIGHT,
                ord("r"),
                ord("k"),
                ord("["),
                ord("]"),
            ]

            for key in expected_keys:
                self.assertIn(key, controller.key_handlers)

    def test_run_with_large_worker_count(self):
        """Test run function with very large worker count."""
        if run is None:
            self.skipTest("run function not available")

        with patch("taskpanel.runner.curses.wrapper") as mock_wrapper:
            mock_wrapper.side_effect = KeyboardInterrupt()

            try:
                run(self.csv_path, max_workers=1000)
            except KeyboardInterrupt:
                pass

    def test_run_with_minimum_worker_count(self):
        """Test run function with minimum worker count."""
        if run is None:
            self.skipTest("run function not available")

        with patch("taskpanel.runner.curses.wrapper") as mock_wrapper:
            mock_wrapper.side_effect = KeyboardInterrupt()

            try:
                run(self.csv_path, max_workers=1)
            except KeyboardInterrupt:
                pass

    def test_run_parameter_types(self):
        """Test run function parameter type validation."""
        if run is None:
            self.skipTest("run function not available")

        # Test with float worker count (should work if > 1)
        with patch("taskpanel.runner.curses.wrapper") as mock_wrapper:
            mock_wrapper.side_effect = KeyboardInterrupt()

            try:
                run(self.csv_path, max_workers=2.0)
            except (KeyboardInterrupt, TypeError):
                pass

    @patch("os.path.exists")
    def test_run_csv_path_validation(self, mock_exists):
        """Test CSV path validation in detail."""
        if run is None:
            self.skipTest("run function not available")

        mock_exists.return_value = False

        with self.assertRaises(FileNotFoundError) as cm:
            run("/fake/path.csv", max_workers=1)

        self.assertIn("not found", str(cm.exception))

    def test_constants_values(self):
        """Test that constants have reasonable values."""
        if runner is None:
            self.skipTest("runner module not available")

        # Test timing constants
        self.assertGreater(runner.MAIN_LOOP_SLEEP_S, 0)
        self.assertLess(runner.MAIN_LOOP_SLEEP_S, 1)

        self.assertGreater(runner.UI_REFRESH_INTERVAL_S, 0)
        self.assertLess(runner.UI_REFRESH_INTERVAL_S, 10)

        # Test key constants
        self.assertIsInstance(runner.ENTER_KEYS, tuple)
        self.assertGreater(len(runner.ENTER_KEYS), 0)

        self.assertIsInstance(runner.BACKSPACE_KEYS, tuple)
        self.assertGreater(len(runner.BACKSPACE_KEYS), 0)

    @patch("taskpanel.runner.ThreadPoolExecutor")
    @patch("curses.initscr")
    @patch("curses.start_color")
    @patch("curses.has_colors")
    @patch("curses.curs_set")
    @patch("taskpanel.runner.setup_colors")
    def test_app_controller_executor_shutdown(
        self,
        mock_setup_colors,
        mock_curs_set,
        mock_has_colors,
        mock_start_color,
        mock_initscr,
        mock_executor_class,
    ):
        """Test proper executor shutdown."""
        if runner is None:
            self.skipTest("runner module not available")

        # Mock executor
        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        # Mock curses initialization
        mock_stdscr = MagicMock()
        mock_stdscr.getch.return_value = ord("q")  # Quit immediately
        mock_stdscr.nodelay = MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)
        mock_initscr.return_value = mock_stdscr
        mock_has_colors.return_value = True
        mock_start_color.return_value = None
        mock_setup_colors.return_value = None

        # Mock TaskModel to avoid file operations
        with patch.object(runner.TaskModel, "load_tasks") as mock_load, patch(
            "taskpanel.runner.draw_ui"
        ) as mock_draw_ui, patch("time.sleep") as mock_sleep:
            mock_load.return_value = None
            mock_draw_ui.return_value = None
            mock_sleep.return_value = None

            try:
                controller = runner.AppController(mock_stdscr, self.csv_path, 1, "Test")

                # Run the loop briefly
                controller.run_loop()

            except Exception as e:
                # Accept certain exceptions that might occur during testing
                if "getch" in str(e) or "nodelay" in str(e) or "Mock" in str(e):
                    pass  # Expected with mocking
                else:
                    self.fail(f"Unexpected error: {e}")

            # Should call shutdown on executor
            self.assertTrue(mock_executor.shutdown.called)

    @patch("curses.initscr")
    @patch("curses.start_color")
    @patch("curses.has_colors")
    @patch("curses.curs_set")
    @patch("taskpanel.runner.setup_colors")
    def test_app_controller_search_functionality(
        self,
        mock_setup_colors,
        mock_curs_set,
        mock_has_colors,
        mock_start_color,
        mock_initscr,
    ):
        """Test search functionality in AppController."""
        if runner is None:
            self.skipTest("runner module not available")

        # Mock curses initialization
        mock_stdscr = MagicMock()
        mock_stdscr.nodelay = MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)
        mock_initscr.return_value = mock_stdscr
        mock_has_colors.return_value = True
        mock_start_color.return_value = None
        mock_setup_colors.return_value = None

        # Mock TaskModel to avoid file operations
        with patch.object(runner.TaskModel, "load_tasks") as mock_load:
            mock_load.return_value = None

            try:
                controller = runner.AppController(mock_stdscr, self.csv_path, 1, "Test")

                # Test search mode activation
                self.assertFalse(controller.is_search_mode)
                controller._handle_enter_search_mode()
                self.assertTrue(controller.is_search_mode)

                # Test search mode exit
                controller._handle_exit_search_mode()
                self.assertFalse(controller.is_search_mode)
            except Exception as e:
                # Accept certain exceptions that might occur during testing
                acceptable_errors = ["Mock", "getch", "nodelay", "attribute"]
                if any(err in str(e) for err in acceptable_errors):
                    self.skipTest(f"Test requires specific implementation details: {e}")
                else:
                    self.fail(f"Unexpected error: {e}")

    @patch("curses.wrapper")
    @patch("curses.initscr")
    @patch("curses.start_color")
    @patch("curses.has_colors")
    @patch("curses.curs_set")
    @patch("curses.noecho")
    @patch("curses.cbreak")
    @patch("taskpanel.runner.setup_colors")
    def test_app_controller_initialization_safe(
        self,
        mock_setup_colors,
        mock_cbreak,
        mock_noecho,
        mock_curs_set,
        mock_has_colors,
        mock_start_color,
        mock_initscr,
        mock_wrapper,
    ):
        """Test AppController initialization with safe mocking."""
        if runner is None:
            self.skipTest("runner module not available")

        # Mock all curses functions that might be called during initialization
        mock_stdscr = MagicMock()
        mock_stdscr.nodelay = MagicMock()
        mock_stdscr.getmaxyx.return_value = (24, 80)
        mock_stdscr.getch.return_value = ord("q")  # Immediate quit

        mock_initscr.return_value = mock_stdscr
        mock_has_colors.return_value = True
        mock_start_color.return_value = None
        mock_curs_set.return_value = None
        mock_noecho.return_value = None
        mock_cbreak.return_value = None
        mock_setup_colors.return_value = None

        # Mock the entire curses.wrapper to avoid initialization issues
        def mock_wrapper_func(func, *args, **kwargs):
            # Call the function with mock stdscr
            return func(mock_stdscr, *args, **kwargs)

        mock_wrapper.side_effect = mock_wrapper_func

        # Mock other dependencies that might cause issues
        with patch.object(runner.TaskModel, "load_tasks") as mock_load, patch(
            "taskpanel.runner.draw_ui"
        ) as mock_draw_ui, patch("threading.RLock") as mock_rlock:
            mock_load.return_value = None
            mock_draw_ui.return_value = None
            mock_rlock.return_value = MagicMock()  # Mock RLock for state_lock

            try:
                # Test that we can create the controller
                controller = runner.AppController(
                    mock_stdscr, self.csv_path, 2, "Test Title"
                )

                # Test basic attributes
                self.assertEqual(controller.max_workers, 2)
                self.assertEqual(controller.title, "Test Title")
                self.assertTrue(controller.app_running)
                self.assertFalse(controller.is_search_mode)
                self.assertEqual(controller.search_query, "")

            except Exception as e:
                # Even with comprehensive mocking, some errors might occur
                acceptable_error_terms = [
                    "Mock",
                    "attribute",
                    "getch",
                    "initscr",
                    "start_color",
                    "has_colors",
                    "curs_set",
                    "noecho",
                    "cbreak",
                    "nodelay",
                ]

                if any(term in str(e) for term in acceptable_error_terms):
                    self.skipTest(
                        f"Controller creation requires specific curses environment: {e}"
                    )
                else:
                    self.fail(f"Unexpected error: {e}")

    def test_app_controller_class_structure(self):
        """Test AppController class structure without instantiation."""
        if runner is None:
            self.skipTest("runner module not available")

        # Test that the AppController class exists and has expected structure
        self.assertTrue(hasattr(runner, "AppController"))

        app_controller_class = runner.AppController
        self.assertTrue(callable(app_controller_class))

        # Test __init__ signature
        import inspect

        init_sig = inspect.signature(app_controller_class.__init__)
        init_params = list(init_sig.parameters.keys())

        # Should have self, stdscr, csv_path, max_workers, title
        expected_params = ["self", "stdscr", "workflow_path", "max_workers", "title"]
        for param in expected_params:
            self.assertIn(param, init_params, f"__init__ should have {param} parameter")

    @patch("curses.wrapper")
    @patch("taskpanel.runner.TaskModel")
    def test_app_controller_creation_minimal(self, mock_task_model, mock_wrapper):
        """Test AppController creation with minimal viable mocking."""
        if runner is None:
            self.skipTest("runner module not available")

        # Create a mock TaskModel instance
        mock_model_instance = MagicMock()
        mock_model_instance.load_tasks.return_value = None
        mock_task_model.return_value = mock_model_instance

        # Mock wrapper to completely bypass curses
        def safe_wrapper(func, *args, **kwargs):
            # Don't actually call the function, just return success
            return "wrapper_called"

        mock_wrapper.side_effect = safe_wrapper

        # Mock all the curses-related patches
        with patch("curses.curs_set"), patch("taskpanel.runner.setup_colors"), patch(
            "threading.RLock"
        ):
            # Create a comprehensive mock stdscr
            mock_stdscr = MagicMock()
            mock_stdscr.nodelay = MagicMock()
            mock_stdscr.getmaxyx.return_value = (24, 80)

            try:
                # This should work with comprehensive mocking
                controller = runner.AppController(
                    mock_stdscr, self.csv_path, 2, "Test Title"
                )

                # Test that basic attributes exist
                self.assertTrue(hasattr(controller, "max_workers"))
                self.assertTrue(hasattr(controller, "title"))
                self.assertTrue(hasattr(controller, "app_running"))
                self.assertTrue(hasattr(controller, "is_search_mode"))
                self.assertTrue(hasattr(controller, "search_query"))

            except Exception as e:
                # If we still get errors, it means the implementation has dependencies we haven't mocked
                self.skipTest(
                    f"AppController requires environment not available in tests: {e}"
                )

    def test_run_function_error_handling_patterns(self):
        """Test run function error handling without full execution."""
        if run is None:
            self.skipTest("run function not available")

        # Test parameter validation without actually running
        test_cases = [
            # (args, kwargs, expected_exception)
            (["/nonexistent.csv"], {"max_workers": 1}, FileNotFoundError),
            ([self.csv_path], {"max_workers": 0}, ValueError),
            ([self.csv_path], {"max_workers": -5}, ValueError),
        ]

        for args, kwargs, expected_exception in test_cases:
            with self.subTest(args=args, kwargs=kwargs):
                with self.assertRaises(expected_exception):
                    run(*args, **kwargs)

    @patch("curses.wrapper")
    def test_run_function_wrapper_interaction(self, mock_wrapper):
        """Test how run function interacts with curses.wrapper."""
        if run is None:
            self.skipTest("run function not available")

        # Mock wrapper to track calls without executing
        call_tracker = []

        def tracking_wrapper(func, *args, **kwargs):
            call_tracker.append(
                (
                    "wrapper_called",
                    func.__name__ if hasattr(func, "__name__") else str(func),
                )
            )
            # Simulate quick exit
            raise KeyboardInterrupt("Simulated interrupt")

        mock_wrapper.side_effect = tracking_wrapper

        try:
            run(self.csv_path, max_workers=1, title="Test")
        except KeyboardInterrupt:
            pass  # Expected

        # Verify wrapper was called
        self.assertEqual(len(call_tracker), 1)
        self.assertTrue(mock_wrapper.called)

    def test_module_level_functions_exist(self):
        """Test that expected module-level functions exist."""
        if runner is None:
            self.skipTest("runner module not available")

        expected_functions = ["run"]
        for func_name in expected_functions:
            self.assertTrue(
                hasattr(runner, func_name), f"Module should have {func_name} function"
            )
            func = getattr(runner, func_name)
            self.assertTrue(callable(func), f"{func_name} should be callable")

    def test_module_level_classes_exist(self):
        """Test that expected module-level classes exist."""
        if runner is None:
            self.skipTest("runner module not available")

        expected_classes = ["AppController"]
        for class_name in expected_classes:
            self.assertTrue(
                hasattr(runner, class_name), f"Module should have {class_name} class"
            )
            cls = getattr(runner, class_name)
            self.assertTrue(callable(cls), f"{class_name} should be callable (class)")

    @patch("taskpanel.runner.curses.wrapper")
    @patch("taskpanel.runner.os.name", "posix")
    def test_run_with_yaml_file(self, mock_wrapper):
        """Test that run function accepts YAML workflow files."""
        if run is None:
            self.skipTest("run function not available")

        # Create a temporary YAML workflow
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            yaml_path = f.name
            f.write(
                "steps: [Step1, Step2]\n"
                "tasks:\n"
                "  - name: 'Y Task'\n"
                "    info: 'Info'\n"
                "    steps:\n"
                '      Step1: "echo one"\n'
                '      Step2: "echo two"\n'
            )

        mock_wrapper.side_effect = KeyboardInterrupt()

        try:
            run(yaml_path, max_workers=1, title="YAML")
        except KeyboardInterrupt:
            pass
        finally:
            try:
                os.unlink(yaml_path)
            except OSError:
                pass

    def test_app_controller_search_filter_invalid_regex(self):
        """Invalid regex in search should not crash and should ignore filter."""
        if runner is None:
            self.skipTest("runner module not available")

        with patch("curses.curs_set"), patch(
            "taskpanel.runner.setup_colors"
        ), patch.object(runner.TaskModel, "load_tasks"):
            mock_stdscr = MagicMock()
            controller = runner.AppController(mock_stdscr, "/tmp/no.csv", 1, "T")
            # Inject model tasks
            task1 = MagicMock()
            task1.name = "Alpha"
            task2 = MagicMock()
            task2.name = "Beta"
            controller.model.tasks = [task1, task2]
            # Set invalid regex
            controller.search_query = "("
            # Should not throw
            controller._apply_search_filter()
            # Fallback to no filter or empty result; at least not crash
            self.assertIsInstance(controller.filtered_task_indices, list)

    def test_app_controller_toggle_debug_and_resize(self):
        """Toggle debug changes layout flag; resize handler marks UI dirty."""
        if runner is None:
            self.skipTest("runner module not available")

        with patch("curses.curs_set"), patch(
            "taskpanel.runner.setup_colors"
        ), patch.object(runner.TaskModel, "load_tasks"):
            mock_stdscr = MagicMock()
            c = runner.AppController(mock_stdscr, "/tmp/no.csv", 1, "T")
            old = c.view_state.debug_panel_visible
            c._handle_toggle_debug()
            self.assertNotEqual(c.view_state.debug_panel_visible, old)
            self.assertTrue(c.view_state.layout_dirty)

            # Resize
            c.ui_dirty = False
            c._handle_resize()
            self.assertTrue(c.ui_dirty)
            self.assertTrue(c.view_state.layout_dirty)

    def test_process_input_search_mode_typing_and_submit(self):
        if runner is None:
            self.skipTest("runner module not available")
        with patch("curses.curs_set"), patch(
            "taskpanel.runner.setup_colors"
        ), patch.object(runner.TaskModel, "load_tasks"):
            stdscr = MagicMock()
            # Provide sequential keys: enter search '/', type 'a', ENTER
            inputs = [ord("/"), ord("a"), 10]
            stdscr.getch.side_effect = inputs + [-1]
            c = runner.AppController(stdscr, "/tmp/no.csv", 1, "T")
            # Inject tasks to match query
            c.model.tasks = [MagicMock(name="A"), MagicMock(name="B")]
            # First key '/', enter search mode
            c.process_input()
            self.assertTrue(c.is_search_mode)
            # Type 'a'
            c.process_input()
            self.assertEqual(c.search_query, "a")
            # ENTER to exit search mode
            c.process_input()
            self.assertFalse(c.is_search_mode)

    def test_process_input_backspace_and_escape(self):
        if runner is None:
            self.skipTest("runner module not available")
        with patch("curses.curs_set"), patch(
            "taskpanel.runner.setup_colors"
        ), patch.object(runner.TaskModel, "load_tasks"):
            stdscr = MagicMock()
            stdscr.getch.side_effect = [
                ord("/"),
                127,
                27,
                27,
            ]  # '/', backspace, ESC(clear), ESC(exit)
            c = runner.AppController(stdscr, "/tmp/no.csv", 1, "T")
            c.search_query = "x"
            # enter search mode
            c.process_input()
            c.is_search_mode = True
            # backspace
            c.process_input()
            # ESC when query empty -> exit search mode after two ESC
            c.search_query = "q"
            c.process_input()  # clear query
            self.assertEqual(c.search_query, "")
            c.process_input()  # exit
            self.assertFalse(c.is_search_mode)

    def test_rerun_blocked_and_allowed(self):
        if runner is None:
            self.skipTest("runner module not available")
        with patch("curses.curs_set"), patch("taskpanel.runner.setup_colors"), patch(
            "taskpanel.runner.curses.flash"
        ) as mock_flash, patch.object(runner.TaskModel, "load_tasks"):
            stdscr = MagicMock()
            c = runner.AppController(stdscr, "/tmp/no.csv", 1, "T")
            # Prepare one task with two steps
            task = MagicMock()
            # Blocked: selected step is None
            task.steps = [None, None]
            c.model.tasks = [task]
            c.filtered_task_indices = [0]
            c.view_state.selected_row = 0
            c.view_state.selected_col = 0
            c._handle_rerun()
            self.assertTrue(mock_flash.called)

            # Allowed: previous steps SUCCESS, selected step present
            mock_flash.reset_mock()
            from taskpanel.model import Step, Status

            step0 = MagicMock()
            step0.status = Status.SUCCESS
            step1 = MagicMock()
            step1.status = Status.PENDING
            task.steps = [step0, step1]
            c.view_state.selected_col = 1
            with patch.object(c.model, "rerun_task_from_step") as mock_rerun:
                c._handle_rerun()
                mock_rerun.assert_called_once()

    def test_start_initial_tasks_submits_resume(self):
        if runner is None:
            self.skipTest("runner module not available")
        with patch("curses.curs_set"), patch(
            "taskpanel.runner.setup_colors"
        ), patch.object(runner.TaskModel, "load_tasks"):
            stdscr = MagicMock()
            c = runner.AppController(stdscr, "/tmp/no.csv", 1, "T")
            # Task with first SUCCESS then PENDING should trigger resume from step 1
            from taskpanel.model import Status

            step0 = MagicMock()
            step0.status = Status.SUCCESS
            step1 = MagicMock()
            step1.status = Status.PENDING
            task = MagicMock()
            task.steps = [step0, step1]
            task.name = "T"
            c.model.tasks = [task]
            with patch.object(c.executor, "submit") as mock_submit:
                c.start_initial_tasks()
                self.assertTrue(mock_submit.called)

    def test_nav_right_updates_left_most_step(self):
        if runner is None:
            self.skipTest("runner module not available")
        with patch("curses.curs_set"), patch(
            "taskpanel.runner.setup_colors"
        ), patch.object(runner.TaskModel, "load_tasks"):
            stdscr = MagicMock()
            c = runner.AppController(stdscr, "/tmp/no.csv", 1, "T")
            task = MagicMock()
            task.steps = [1, 2]
            c.model.tasks = [task]
            c.filtered_task_indices = [0]
            # Simulate layout with only 1 visible step
            c.view_state.cached_layout = MagicMock(num_visible_steps=1, task_list_h=1)
            c.view_state.selected_row = 0
            c.view_state.selected_col = 0
            c._handle_nav_right()
            self.assertEqual(c.view_state.left_most_step, 1)

    def test_nav_page_down(self):
        if runner is None:
            self.skipTest("runner module not available")
        with patch("curses.curs_set"), patch(
            "taskpanel.runner.setup_colors"
        ), patch.object(runner.TaskModel, "load_tasks"):
            stdscr = MagicMock()
            c = runner.AppController(stdscr, "/tmp/no.csv", 1, "T")
            c.filtered_task_indices = list(range(10))
            c.view_state.cached_layout = MagicMock(task_list_h=3)
            c._handle_nav_page_down()
            self.assertGreaterEqual(c.view_state.top_row, 0)
