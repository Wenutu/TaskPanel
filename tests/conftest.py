#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test configuration and fixtures for TaskPanel tests.
"""

import csv
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_csv_content():
    """Sample CSV content for testing."""
    return [
        ["TaskName", "Info", "Step1", "Step2"],
        ["Test-Task-1", "Test task 1", "echo 'Step 1'", "echo 'Step 2'"],
        ["Test-Task-2", "Test task 2", "sleep 1", "echo 'Done'"],
    ]


@pytest.fixture
def sample_csv_file(temp_dir, sample_csv_content):
    """Create a sample CSV file for testing."""
    csv_file = temp_dir / "test_tasks.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for row in sample_csv_content:
            writer.writerow(row)
    return csv_file


@pytest.fixture
def sample_script_dir(temp_dir):
    """Create sample scripts directory."""
    scripts_dir = temp_dir / "scripts"
    scripts_dir.mkdir()

    # Create a simple test script
    test_script = scripts_dir / "test.sh"
    test_script.write_text("#!/bin/bash\necho 'Test script executed'\n")
    test_script.chmod(0o755)

    return scripts_dir
