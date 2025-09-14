# taskpanel/__init__.py

"""
TaskPanel: A Robust Interactive Terminal Task Runner.

This package provides a terminal-based tool to run, monitor, and manage
multi-step parallel tasks defined in a simple CSV file.
"""

__version__ = "1.0.1"

from .model import TaskLoadError

# Expose the primary `run` function for programmatic use and the specific
# exception for better error handling by the calling script.
from .runner import run

__all__ = ["run", "TaskLoadError"]
