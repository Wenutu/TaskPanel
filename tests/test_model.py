#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_model.py

Simple tests for TaskPanel model module - focused on packaging and basic functionality.
"""

import os
import sys
import unittest

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from taskpanel import model
    from taskpanel.model import Status, TaskModel
except ImportError as e:
    print(f"Warning: Could not import model module: {e}")
    model = None
    TaskModel = None
    Status = None


class TestModel(unittest.TestCase):
    """Simple model tests for packaging validation."""

    def test_model_module_import(self):
        """Test that model module can be imported."""
        self.assertIsNotNone(model, "Model module should be importable")

    def test_task_model_class_exists(self):
        """Test that TaskModel class exists."""
        if TaskModel is None:
            self.skipTest("TaskModel not available")

        self.assertTrue(callable(TaskModel), "TaskModel should be a class")

    def test_status_enum_exists(self):
        """Test that Status enum exists."""
        if Status is None:
            self.skipTest("Status enum not available")

        # Test basic status values
        self.assertTrue(hasattr(Status, "PENDING"))
        self.assertTrue(hasattr(Status, "SUCCESS"))
        self.assertTrue(hasattr(Status, "FAILED"))


if __name__ == "__main__":
    unittest.main()
