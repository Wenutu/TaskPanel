#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Command-line interface for TaskPanel.
"""

import argparse
import os
import sys

from . import TaskLoadError, run


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="TaskPanel: A Robust Interactive Terminal Task Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  taskpanel tasks.csv                    # Run with default settings
  taskpanel tasks.csv --workers 8       # Run with 8 parallel workers
  taskpanel tasks.csv --title "My App"  # Run with custom title
        """,
    )

    parser.add_argument(
        "csv_file", help="Path to the CSV file containing task definitions"
    )

    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=os.cpu_count() or 4,
        help="Maximum number of parallel workers (default: %(default)s)",
    )

    parser.add_argument(
        "--title",
        "-t",
        default="TaskPanel",
        help="Application title displayed in the UI (default: %(default)s)",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"TaskPanel {__import__('taskpanel').__version__}",
    )

    args = parser.parse_args()

    # Validate CSV file exists
    if not os.path.isfile(args.csv_file):
        print(f"Error: CSV file '{args.csv_file}' not found.", file=sys.stderr)
        sys.exit(1)

    # Validate workers count
    if args.workers <= 0:
        print(
            f"Error: Number of workers must be positive, got {args.workers}.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Starting TaskPanel for workflow: {args.csv_file}")
    print(f"Max workers: {args.workers}")
    print(f"Title: {args.title}")
    print()

    try:
        run(csv_path=args.csv_file, max_workers=args.workers, title=args.title)
    except FileNotFoundError as e:
        print("Error: Could not find the specified CSV file.", file=sys.stderr)
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except TaskLoadError as e:
        print("Error: Failed to load tasks from the CSV file.", file=sys.stderr)
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Operating System Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        # TaskPanel handles this gracefully, but we catch it here for clean exit
        print("\nApplication was interrupted by the user.")
        sys.exit(0)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
