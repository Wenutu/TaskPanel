#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_view.py

Simple tests for TaskPanel view module - focused on packaging and basic functionality.
"""

import os
import sys
import unittest

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from taskpanel import view
    from taskpanel.view import ViewState, format_duration
except ImportError as e:
    print(f"Warning: Could not import view module: {e}")
    view = None
    format_duration = None
    ViewState = None


class TestView(unittest.TestCase):
    """Simple view tests for packaging validation."""

    def test_view_module_import(self):
        """Test that view module can be imported."""
        self.assertIsNotNone(view, "View module should be importable")

    def test_format_duration_function_exists(self):
        """Test that format_duration function exists."""
        if format_duration is None:
            self.skipTest("format_duration not available")

        self.assertTrue(callable(format_duration), "format_duration should be callable")

    def test_view_state_class_exists(self):
        """Test that ViewState class exists."""
        if ViewState is None:
            self.skipTest("ViewState not available")

        self.assertTrue(callable(ViewState), "ViewState should be a class")


if __name__ == "__main__":
    unittest.main()
