#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_cli.py

Simple tests for TaskPanel CLI module - focused on packaging and basic functionality.
"""

import os
import sys
import unittest

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from taskpanel import cli
except ImportError as e:
    print(f"Warning: Could not import CLI module: {e}")
    cli = None


class TestCLI(unittest.TestCase):
    """Simple CLI tests for packaging validation."""

    def test_cli_module_import(self):
        """Test that CLI module can be imported."""
        self.assertIsNotNone(cli, "CLI module should be importable")

    def test_main_function_exists(self):
        """Test that main function exists."""
        if cli is None:
            self.skipTest("CLI module not available")

        self.assertTrue(hasattr(cli, "main"), "CLI should have main function")
        self.assertTrue(callable(cli.main), "main should be callable")


if __name__ == "__main__":
    unittest.main()
