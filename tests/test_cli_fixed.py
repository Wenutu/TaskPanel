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

# Add the src directory to the path
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
    """Tests for CLI functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.csv_path = os.path.join(self.test_dir, "test.csv")
        with open(self.csv_path, "w") as f:
            f.write("TaskName,Info,Command\nTest Task,Test Info,echo test\n")

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    def test_cli_module_import(self):
        """Test that CLI module can be imported."""
        self.assertIsNotNone(cli, "CLI module should be importable")

    @patch("taskpanel.cli.run")
    def test_cli_basic_functionality(self, mock_run):
        """Test basic CLI functionality."""
        test_args = ["taskpanel", self.csv_path]
        with patch.object(sys, "argv", test_args):
            cli.main()

        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        self.assertEqual(kwargs.get("csv_path"), self.csv_path)
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
            csv_path=self.csv_path, max_workers=10, title="My Project"
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
            f"Expected 'not found' in stderr calls: {stderr_calls}"
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
            f"Expected 'must be positive' in stderr calls: {stderr_calls}"
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

    def test_cli_workers_type_validation(self):
        """Test CLI validates worker count type."""
        test_args = ["taskpanel", self.csv_path, "--workers", "abc"]
        with patch.object(sys, "argv", test_args):
            # argparse will raise SystemExit for invalid int value
            with self.assertRaises(SystemExit) as cm:
                cli.main()
            
            # In Python 3.6, argparse raises SystemExit with code 2 for argument errors
            self.assertEqual(cm.exception.code, 2)

    def test_cli_argparse_error_handling(self):
        """Test argparse error handling in Python 3.6 compatible way."""
        # Test invalid worker count with different approach
        test_args = ["taskpanel", self.csv_path, "--workers", "invalid"]
        
        # Capture stderr to verify error message
        from io import StringIO
        captured_stderr = StringIO()
        
        with patch.object(sys, "argv", test_args), \
             patch("sys.stderr", captured_stderr):
            
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
            f"Expected 'must be positive' in stderr calls: {stderr_calls}"
        )

    def test_cli_help_exit_code(self):
        """Test that help exits with code 0."""
        test_args = ["taskpanel", "--help"]
        with patch.object(sys, "argv", test_args):
            with self.assertRaises(SystemExit) as cm:
                cli.main()
            
            # Help should exit with code 0
            self.assertEqual(cm.exception.code, 0)

    @patch("taskpanel.cli.run")
    def test_cli_success_path(self, mock_run):
        """Test successful CLI execution path."""
        test_args = ["taskpanel", self.csv_path, "--workers", "2", "--title", "Test"]
        with patch.object(sys, "argv", test_args):
            cli.main()

        mock_run.assert_called_once_with(
            csv_path=self.csv_path, max_workers=2, title="Test"
        )

    def test_cli_error_message_format(self):
        """Test error message formatting."""
        from io import StringIO
        
        # Test file not found error
        test_args = ["taskpanel", "/does/not/exist.csv"]
        captured_stderr = StringIO()
        
        with patch.object(sys, "argv", test_args), \
             patch("sys.stderr", captured_stderr), \
             patch("sys.exit"):
            
            try:
                cli.main()
            except SystemExit:
                pass
            
            stderr_output = captured_stderr.getvalue()
            self.assertIn("Error:", stderr_output)
            self.assertIn("not found", stderr_output)

    @patch("taskpanel.cli.run")
    def test_cli_short_options(self, mock_run):
        """Test CLI with short option flags."""
        test_args = [
            "taskpanel", self.csv_path, 
            "-w", "5", "-t", "Short Title"
        ]
        with patch.object(sys, "argv", test_args):
            cli.main()

        mock_run.assert_called_once_with(
            csv_path=self.csv_path, max_workers=5, title="Short Title"
        )

    @patch("taskpanel.cli.run")
    def test_cli_long_title(self, mock_run):
        """Test CLI with very long title."""
        long_title = "x" * 1000
        test_args = ["taskpanel", self.csv_path, "--title", long_title]
        with patch.object(sys, "argv", test_args):
            cli.main()

        mock_run.assert_called_once_with(
            csv_path=self.csv_path, 
            max_workers=os.cpu_count() or 4, 
            title=long_title
        )

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

    @patch("taskpanel.cli.run")
    def test_cli_unicode_paths(self, mock_run):
        """Test CLI with Unicode file paths."""
        try:
            unicode_path = os.path.join(self.test_dir, "测试文件.csv")
            with open(unicode_path, "w", encoding='utf-8') as f:
                f.write("TaskName,Info,Command\n")

            test_args = ["taskpanel", unicode_path]
            with patch.object(sys, "argv", test_args):
                cli.main()

            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            self.assertEqual(kwargs.get("csv_path"), unicode_path)
        except (UnicodeEncodeError, UnicodeDecodeError):
            self.skipTest("Filesystem doesn't support Unicode filenames")
        except Exception as e:
            if "encoding" in str(e).lower():
                self.skipTest("Unicode handling issues in Python 3.6 environment")
            else:
                raise


if __name__ == "__main__":
    unittest.main()
