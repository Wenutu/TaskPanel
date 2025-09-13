#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_package.py

Simple tests for TaskPanel package integration - focused on packaging validation.
"""

import os
import sys
import unittest
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    import taskpanel
    from taskpanel import TaskLoadError
except ImportError as e:
    print(f"Warning: Could not import taskpanel package: {e}")
    taskpanel = None
    TaskLoadError = None


class TestPackage(unittest.TestCase):
    """Simple package tests for packaging validation."""

    def test_package_import(self):
        """Test that main package can be imported."""
        self.assertIsNotNone(taskpanel, "TaskPanel package should be importable")

    def test_package_has_version(self):
        """Test that package has version."""
        if taskpanel is None:
            self.skipTest("TaskPanel package not available")

        self.assertTrue(hasattr(taskpanel, "__version__"))
        self.assertIsInstance(taskpanel.__version__, str)

    def test_main_exports_exist(self):
        """Test that main package exports exist."""
        if taskpanel is None:
            self.skipTest("TaskPanel package not available")

        # Test main exports
        self.assertTrue(hasattr(taskpanel, "run"))
        self.assertTrue(hasattr(taskpanel, "TaskLoadError"))


class TestProjectStructure(unittest.TestCase):
    """Test project structure for packaging."""

    def setUp(self):
        """Set up test fixtures."""
        self.project_root = Path(__file__).parent.parent

    def test_src_directory_exists(self):
        """Test that src directory exists."""
        src_dir = self.project_root / "src" / "taskpanel"
        self.assertTrue(src_dir.exists())
        self.assertTrue(src_dir.is_dir())

    def test_package_files_exist(self):
        """Test that package files exist."""
        src_dir = self.project_root / "src" / "taskpanel"
        required_files = ["__init__.py", "cli.py", "model.py", "runner.py", "view.py"]

        for filename in required_files:
            file_path = src_dir / filename
            self.assertTrue(file_path.exists(), f"{filename} should exist")

    def test_config_files_exist(self):
        """Test that configuration files exist."""
        config_files = ["pyproject.toml", "setup.py", "README.md"]

        for filename in config_files:
            file_path = self.project_root / filename
            self.assertTrue(file_path.exists(), f"{filename} should exist")


if __name__ == "__main__":
    unittest.main()
