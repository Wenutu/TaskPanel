#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test runner script for TaskPanel with coverage reporting.
"""

import subprocess
import sys
import os


def run_tests():
    """Run all tests with coverage."""
    # Change to project directory
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    print("Running TaskPanel tests with coverage...")
    print("=" * 60)

    # Run tests with coverage
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
        "--cov=taskpanel",
        "--cov-report=term-missing",
        "--cov-report=html",
        "--cov-branch",
    ]

    try:
        result = subprocess.run(cmd, check=False, capture_output=False)

        if result.returncode == 0:
            print("\n" + "=" * 60)
            print("✅ All tests passed!")
            print("📊 Coverage report generated in htmlcov/")
        else:
            print("\n" + "=" * 60)
            print("❌ Some tests failed.")

        return result.returncode

    except FileNotFoundError:
        print("❌ pytest not found. Please install it: pip install pytest pytest-cov")
        return 1
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
