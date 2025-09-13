#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_runner.py

Simple tests for TaskPanel runner module - focused on packaging and basic functionality.
"""

import os
import sys
import unittest

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from taskpanel import runner
    from taskpanel.runner import run
except ImportError as e:
    print(f"Warning: Could not import runner module: {e}")
    runner = None
    run = None


class TestRunner(unittest.TestCase):
    """Simple runner tests for packaging validation."""

    def test_runner_module_import(self):
        """Test that runner module can be imported."""
        self.assertIsNotNone(runner, "Runner module should be importable")

    def test_run_function_exists(self):
        """Test that run function exists."""
        if run is None:
            self.skipTest("run function not available")

        self.assertTrue(callable(run), "run should be callable")


if __name__ == "__main__":
    unittest.main()
