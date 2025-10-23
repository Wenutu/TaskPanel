#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_cli.py

Tests for TaskPanel CLI module.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from taskpanel import cli
    from taskpanel import __version__ as taskpanel_version
except ImportError as e:
    print(f"Warning: Could not import CLI module: {e}")
    cli = None
    taskpanel_version = "unknown"


@unittest.skipIf(cli is None, "taskpanel.cli module not available for testing.")
class TestCLI(unittest.TestCase):
    """In-depth CLI tests."""

    def setUp(self):
        """Set up a temporary directory and a dummy CSV file."""
        self.test_dir = tempfile.mkdtemp()
        self.csv_path = os.path.join(self.test_dir, "tasks.csv")
        with open(self.csv_path, "w") as f:
            f.write("TaskName,Info,Command\n")

    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.test_dir)

    def test_cli_module_import(self):
        """Test that CLI module can be imported."""
        self.assertIsNotNone(cli, "CLI module should be importable")

    def test_main_function_exists(self):
        """Test that main function exists."""
        self.assertTrue(hasattr(cli, "main"), "CLI should have main function")
        self.assertTrue(callable(cli.main), "main should be callable")

    @patch("taskpanel.cli.run")
    def test_cli_with_default_args(self, mock_run):
        """Test CLI with default arguments."""
        test_args = ["taskpanel", self.csv_path]
        with patch.object(sys, "argv", test_args):
            cli.main()

        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        self.assertEqual(kwargs.get("workflow_path"), self.csv_path)
        self.assertEqual(kwargs.get("title"), "TaskPanel")
        # Default workers depends on os.cpu_count(), so we just check it's a positive integer
        self.assertIsInstance(kwargs.get("max_workers"), int)
        self.assertGreater(kwargs.get("max_workers"), 0)

    @patch("taskpanel.cli.run")
    def test_cli_with_custom_args(self, mock_run):
        """Test CLI with custom arguments for workers and title."""
        test_args = [
            "taskpanel",
            self.csv_path,
            "--workers",
            "10",
            "--title",
            "My Project",
        ]
        with patch.object(sys, "argv", test_args):
            cli.main()

        mock_run.assert_called_once_with(
            workflow_path=self.csv_path, max_workers=10, title="My Project"
        )

    @patch("sys.exit")
    @patch("sys.stderr")
    def test_cli_file_not_found(self, mock_stderr, mock_exit):
        """Test CLI exits if CSV file is not found."""
        test_args = ["taskpanel", "/non/existent/file.csv"]
        with patch.object(sys, "argv", test_args):
            cli.main()

        mock_exit.assert_called_with(1)
        # Check that an error message was printed to stderr
        stderr_calls = [str(call) for call in mock_stderr.write.call_args_list]
        self.assertTrue(
            any("not found" in call for call in stderr_calls),
            f"Expected 'not found' in stderr calls: {stderr_calls}",
        )

    @patch("sys.exit")
    @patch("sys.stderr")
    def test_cli_invalid_workers(self, mock_stderr, mock_exit):
        """Test CLI exits if worker count is invalid."""
        test_args = ["taskpanel", self.csv_path, "-w", "0"]
        with patch.object(sys, "argv", test_args):
            cli.main()

        mock_exit.assert_called_with(1)
        # Check that an error message was printed to stderr
        stderr_calls = [str(call) for call in mock_stderr.write.call_args_list]
        self.assertTrue(
            any("must be positive" in call for call in stderr_calls),
            f"Expected 'must be positive' in stderr calls: {stderr_calls}",
        )

    def test_version_action(self):
        """Test that --version prints the version and exits."""
        # Provide the required csv_file argument along with --version
        test_args = ["taskpanel", self.csv_path, "--version"]
        with patch.object(sys, "argv", test_args):
            # argparse's version action raises SystemExit directly
            with self.assertRaises(SystemExit) as cm:
                cli.main()

            # Version action should exit with code 0
            self.assertEqual(cm.exception.code, 0)

    @patch("taskpanel.cli.run")
    def test_cli_help_message(self, mock_run):
        """Test CLI help message."""
        test_args = ["taskpanel", "--help"]
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                cli.main()

            # Help should exit with code 0
            self.assertEqual(cm.exception.code, 0)

    @patch("taskpanel.cli.run")
    def test_cli_short_options(self, mock_run):
        """Test CLI with short option flags."""
        test_args = [
            "taskpanel",
            self.csv_path,
            "-w",
            "5",
            "-t",
            "Short Title",
        ]
        with patch.object(sys, "argv", test_args):
            cli.main()

        mock_run.assert_called_once_with(
            workflow_path=self.csv_path, max_workers=5, title="Short Title"
        )

    def test_cli_workers_type_validation(self):
        """Test CLI validates worker count type."""
        test_args = ["taskpanel", self.csv_path, "--workers", "abc"]
        with patch.object(sys, "argv", test_args):
            # argparse will raise SystemExit for invalid int value
            with self.assertRaises(SystemExit) as cm:
                cli.main()

            # In Python 3.6, argparse raises SystemExit with code 2 for argument errors
            self.assertEqual(cm.exception.code, 2)

    @patch("taskpanel.cli.run")
    def test_cli_long_title(self, mock_run):
        """Test CLI with very long title."""
        long_title = "x" * 1000
        test_args = ["taskpanel", self.csv_path, "--title", long_title]
        with patch.object(sys, "argv", test_args):
            cli.main()

        mock_run.assert_called_once_with(
            workflow_path=self.csv_path,
            max_workers=os.cpu_count(),
            title=long_title,
        )

    @patch("sys.exit")
    @patch("builtins.print")
    def test_cli_permission_error(self, mock_print, mock_exit):
        """Test CLI handles permission errors."""
        # Skip this test on Windows or if we can't change permissions
        if os.name == "nt":
            self.skipTest("Permission test not applicable on Windows")

        # Create a file
        restricted_file = os.path.join(self.test_dir, "restricted.csv")
        with open(restricted_file, "w") as f:
            f.write("TaskName,Info,Command\n")

        try:
            # Make directory unreadable (more reliable than file permissions)
            test_dir_restricted = os.path.join(self.test_dir, "restricted_dir")
            os.makedirs(test_dir_restricted)
            restricted_file_in_dir = os.path.join(test_dir_restricted, "test.csv")
            with open(restricted_file_in_dir, "w") as f:
                f.write("TaskName,Info,Command\n")

            os.chmod(test_dir_restricted, 0o000)

            test_args = ["taskpanel", restricted_file_in_dir]
            with patch.object(sys, "argv", test_args):
                cli.main()

            mock_exit.assert_called_with(1)
        except PermissionError:
            # If we can't change permissions, skip the test
            self.skipTest("Cannot modify permissions for test")
        finally:
            # Restore permissions for cleanup
            try:
                os.chmod(test_dir_restricted, 0o755)
            except:
                pass

    @patch("taskpanel.cli.run")
    def test_cli_unicode_paths(self, mock_run):
        """Test CLI with Unicode file paths."""
        try:
            unicode_path = os.path.join(self.test_dir, "测试文件.csv")
            with open(unicode_path, "w", encoding="utf-8") as f:
                f.write("TaskName,Info,Command\n")

            test_args = ["taskpanel", unicode_path]
            with patch.object(sys, "argv", test_args):
                cli.main()

            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            self.assertEqual(kwargs.get("workflow_path"), unicode_path)
        except UnicodeEncodeError:
            self.skipTest("Filesystem doesn't support Unicode filenames")

    @patch("taskpanel.cli.run")
    def test_cli_relative_paths(self, mock_run):
        """Test CLI with relative file paths."""
        # Create CSV in test directory
        rel_csv = "test_relative.csv"
        full_path = os.path.join(self.test_dir, rel_csv)
        with open(full_path, "w") as f:
            f.write("TaskName,Info,Command\n")

        # Change to test directory and use relative path
        original_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)
            test_args = ["taskpanel", rel_csv]
            with patch.object(sys, "argv", test_args):
                cli.main()
        finally:
            os.chdir(original_cwd)

        mock_run.assert_called_once()

    @patch("sys.exit")
    @patch("builtins.print")
    def test_cli_negative_workers(self, mock_print, mock_exit):
        """Test CLI rejects negative worker count."""
        test_args = ["taskpanel", self.csv_path, "--workers", "-5"]
        with patch.object(sys, "argv", test_args):
            cli.main()

        mock_exit.assert_called_with(1)
        self.assertTrue(
            any("must be positive" in str(call) for call in mock_print.call_args_list)
        )

    def test_version_string_format(self):
        """Test that version string is properly formatted."""
        if hasattr(cli, "__version__") or "taskpanel_version" in globals():
            # Version should be a string
            version = getattr(cli, "__version__", taskpanel_version)
            self.assertIsInstance(version, str)
            self.assertGreater(len(version), 0)

    def test_cli_argparse_error_handling(self):
        """Test argparse error handling in Python 3.6 compatible way."""
        # Test invalid worker count with different approach
        test_args = ["taskpanel", self.csv_path, "--workers", "invalid"]

        # Capture stderr to verify error message
        from io import StringIO

        captured_stderr = StringIO()

        with patch.object(sys, "argv", test_args), patch("sys.stderr", captured_stderr):
            with self.assertRaises(SystemExit) as cm:
                cli.main()

            # argparse error should exit with code 2
            self.assertEqual(cm.exception.code, 2)

            # Check error message was written to stderr
            stderr_output = captured_stderr.getvalue()
            self.assertIn("invalid int value", stderr_output)

    @patch("sys.exit")
    @patch("sys.stderr")
    def test_cli_negative_workers_python36(self, mock_stderr, mock_exit):
        """Test CLI rejects negative worker count (Python 3.6 compatible)."""
        test_args = ["taskpanel", self.csv_path, "--workers", "-5"]
        with patch.object(sys, "argv", test_args):
            cli.main()

        mock_exit.assert_called_with(1)
        stderr_calls = [str(call) for call in mock_stderr.write.call_args_list]
        self.assertTrue(
            any("must be positive" in call for call in stderr_calls),
            f"Expected 'must be positive' in stderr calls: {stderr_calls}",
        )

    def test_cli_help_exit_code(self):
        """Test that help exits with code 0."""
        test_args = ["taskpanel", "--help"]
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                cli.main()

            # Help should exit with code 0
            self.assertEqual(cm.exception.code, 0)

    def test_cli_version_exit_code(self):
        """Test that version exits with code 0."""
        test_args = ["taskpanel", self.csv_path, "--version"]
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                cli.main()

            # Version should exit with code 0
            self.assertEqual(cm.exception.code, 0)

    @patch("taskpanel.cli.run")
    def test_cli_success_path(self, mock_run):
        """Test successful CLI execution path."""
        test_args = ["taskpanel", self.csv_path, "--workers", "2", "--title", "Test"]
        with patch.object(sys, "argv", test_args):
            cli.main()

        mock_run.assert_called_once_with(
            workflow_path=self.csv_path, max_workers=2, title="Test"
        )

    def test_cli_error_message_format(self):
        """Test error message formatting."""
        from io import StringIO

        # Test file not found error
        test_args = ["taskpanel", "/does/not/exist.csv"]
        captured_stderr = StringIO()

        with patch.object(sys, "argv", test_args), patch(
            "sys.stderr", captured_stderr
        ), patch("sys.exit"):
            try:
                cli.main()
            except SystemExit:
                pass

            stderr_output = captured_stderr.getvalue()
            self.assertIn("Error:", stderr_output)
            self.assertIn("not found", stderr_output)

    @patch("taskpanel.cli.run")
    def test_cli_with_yaml_file(self, mock_run):
        """Test CLI with YAML workflow file."""
        yaml_path = os.path.join(self.test_dir, "tasks.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(
                "steps: [A, B]\n"
                "tasks:\n"
                "  - name: T1\n"
                "    info: I1\n"
                "    steps:\n"
                '      A: "echo a"\n'
                '      B: "echo b"\n'
            )

        test_args = ["taskpanel", yaml_path, "-w", "3", "-t", "YAML Title"]
        with patch.object(sys, "argv", test_args):
            cli.main()

        mock_run.assert_called_once_with(
            workflow_path=yaml_path, max_workers=3, title="YAML Title"
        )

    # --- New tests for CSV -> YAML conversion ---

    @patch("sys.exit")
    @patch("sys.stderr")
    def test_cli_to_yaml_rejects_non_csv_input(self, mock_stderr, mock_exit):
        """--to-yaml should reject non-CSV input."""
        dummy_yaml_in = os.path.join(self.test_dir, "in.yaml")
        with open(dummy_yaml_in, "w", encoding="utf-8") as f:
            f.write("steps: []\ntasks: []\n")

        test_args = [
            "taskpanel",
            dummy_yaml_in,
            "--to-yaml",
            os.path.join(self.test_dir, "out.yaml"),
        ]
        with patch.object(sys, "argv", test_args):
            cli.main()

        mock_exit.assert_called_with(1)
        stderr_calls = [str(c) for c in mock_stderr.write.call_args_list]
        self.assertTrue(any("requires a CSV input file" in s for s in stderr_calls))

    def test_cli_to_yaml_conversion_success(self):
        """CSV -> YAML conversion succeeds; multiline Info becomes description."""
        try:
            import yaml  # Needs PyYAML for validation
        except ImportError:
            self.skipTest("PyYAML not installed; skipping conversion test")

        # Prepare CSV with multiline info
        csv_in = os.path.join(self.test_dir, "convert.csv")
        with open(csv_in, "w", encoding="utf-8") as f:
            f.write("TaskName,Info,StepA,StepB\n")
            f.write('T1,"Line1\nLine2",echo A,echo B\n')

        out_yaml = os.path.join(self.test_dir, "out.yaml")
        test_args = ["taskpanel", csv_in, "--to-yaml", out_yaml]
        with patch.object(sys, "argv", test_args):
            cli.main()

        self.assertTrue(os.path.exists(out_yaml))
        # Validate content structure and description field
        with open(out_yaml, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertIsInstance(data, dict)
        self.assertIn("steps", data)
        self.assertIn("tasks", data)
        self.assertEqual(data["steps"], ["StepA", "StepB"])
        self.assertEqual(len(data["tasks"]), 1)
        self.assertEqual(data["tasks"][0]["name"], "T1")
        # description used for multiline info
        self.assertIn("description", data["tasks"][0])
        self.assertNotIn("info", data["tasks"][0])
        self.assertEqual(
            data["tasks"][0]["steps"], {"StepA": "echo A", "StepB": "echo B"}
        )

    def test_cli_to_yaml_creates_parent_dir_and_omits_empty_steps(self):
        """Conversion should create parent dir and omit empty steps."""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed; skipping conversion test")

        csv_in = os.path.join(self.test_dir, "convert2.csv")
        with open(csv_in, "w", encoding="utf-8") as f:
            f.write("TaskName,Info,Build,Test,Deploy\n")
            f.write("T2,Info 2,echo build,,echo deploy\n")  # Empty 'Test'

        out_dir = os.path.join(self.test_dir, "outdir")
        out_yaml = os.path.join(out_dir, "wf.yaml")
        test_args = ["taskpanel", csv_in, "--to-yaml", out_yaml]
        with patch.object(sys, "argv", test_args):
            cli.main()

        self.assertTrue(os.path.isdir(out_dir))
        with open(out_yaml, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertEqual(data["steps"], ["Build", "Test", "Deploy"])
        # 'Test' absent in steps map for task due to empty command
        self.assertEqual(
            data["tasks"][0]["steps"], {"Build": "echo build", "Deploy": "echo deploy"}
        )

    @patch("sys.exit")
    def test_cli_to_yaml_import_error_yaml_package(self, mock_exit):
        """If PyYAML is not installed, conversion should exit with message."""
        # Prepare CSV
        csv_in = os.path.join(self.test_dir, "convert3.csv")
        with open(csv_in, "w", encoding="utf-8") as f:
            f.write("TaskName,Info,Step\nT,Info,echo x\n")

        out_yaml = os.path.join(self.test_dir, "out3.yaml")

        # Patch builtins.__import__ to raise ImportError only for 'yaml'
        import builtins as _bi

        real_import = _bi.__import__

        def fake_import(name, *a, **kw):
            if name == "yaml":
                raise ImportError("No module named yaml")
            return real_import(name, *a, **kw)

        test_args = ["taskpanel", csv_in, "--to-yaml", out_yaml]
        with patch.object(sys, "argv", test_args), patch.object(
            _bi, "__import__", side_effect=fake_import
        ):
            cli.main()
        mock_exit.assert_called_with(1)

    @patch("taskpanel.cli.run")
    def test_cli_to_yaml_does_not_invoke_run(self, mock_run):
        """--to-yaml conversion should not start UI run()."""
        try:
            import yaml  # validate presence
        except ImportError:
            self.skipTest("PyYAML not installed; skipping conversion test")
        csv_in = os.path.join(self.test_dir, "only_convert.csv")
        with open(csv_in, "w", encoding="utf-8") as f:
            f.write("TaskName,Info,Build\nT,Info,echo build\n")
        out_yaml = os.path.join(self.test_dir, "only_convert.yaml")
        test_args = ["taskpanel", csv_in, "--to-yaml", out_yaml]
        with patch.object(sys, "argv", test_args):
            cli.main()
        self.assertTrue(os.path.exists(out_yaml))
        mock_run.assert_not_called()

    @patch("sys.exit")
    @patch("sys.stderr")
    def test_cli_to_yaml_write_failure(self, mock_stderr, mock_exit):
        """Writing YAML to a directory path should fail and exit(1)."""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed; skipping conversion test")
        csv_in = os.path.join(self.test_dir, "wfail.csv")
        with open(csv_in, "w", encoding="utf-8") as f:
            f.write("TaskName,Info,A\nT,Info,echo a\n")
        # Use directory path to trigger OSError on open(..., 'w')
        out_yaml = self.test_dir
        test_args = ["taskpanel", csv_in, "--to-yaml", out_yaml]
        with patch.object(sys, "argv", test_args):
            cli.main()
        mock_exit.assert_called_with(1)
        self.assertTrue(
            any(
                "Failed to write YAML" in str(c)
                for c in mock_stderr.write.call_args_list
            )
        )

    @patch("sys.exit")
    @patch("builtins.print")
    @patch("taskpanel.cli.run")
    def test_cli_run_handles_taskloaderror(self, mock_run, mock_print, mock_exit):
        """run() raising TaskLoadError should be caught and exit(1)."""
        from taskpanel.model import TaskLoadError as TLE

        mock_run.side_effect = TLE("load boom")
        test_args = ["taskpanel", self.csv_path]
        with patch.object(sys, "argv", test_args):
            cli.main()
        mock_exit.assert_called_with(1)
        self.assertTrue(
            any("Failed to load tasks" in str(c) for c in mock_print.call_args_list)
        )

    @patch("sys.exit")
    @patch("builtins.print")
    @patch("taskpanel.cli.run")
    def test_cli_run_handles_oserror(self, mock_run, mock_print, mock_exit):
        """run() raising OSError should be caught and exit(1)."""
        mock_run.side_effect = OSError("os boom")
        test_args = ["taskpanel", self.csv_path]
        with patch.object(sys, "argv", test_args):
            cli.main()
        mock_exit.assert_called_with(1)
        self.assertTrue(
            any("Operating System Error" in str(c) for c in mock_print.call_args_list)
        )
