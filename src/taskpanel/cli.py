#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Command-line interface for TaskPanel.
"""

import argparse
import os
import sys

from . import TaskLoadError, run
from .model import TaskModel


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="TaskPanel: A Robust Interactive Terminal Task Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  taskpanel tasks.csv                    # Run with default settings (CSV)
  taskpanel tasks.yaml                   # Run with YAML workflow
  taskpanel tasks.csv --workers 8       # Run with 8 parallel workers
  taskpanel tasks.yaml --title "My App" # Run with custom title

  # Convert CSV to YAML (no execution)
  taskpanel tasks.csv --to-yaml tasks.yaml
        """,
    )

    parser.add_argument("workflow_path", help="Path to the workflow file (CSV or YAML)")

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

    parser.add_argument(
        "--to-yaml",
        "-y",
        dest="to_yaml",
        help="Convert the CSV workflow to YAML and write to this path, then exit",
    )

    args = parser.parse_args()

    # Validate workflow file exists
    if not os.path.isfile(args.workflow_path):
        print(f"Error: File '{args.workflow_path}' not found.", file=sys.stderr)
        sys.exit(1)

    # Handle CSV to YAML conversion if requested
    if args.to_yaml:
        if not args.workflow_path.lower().endswith(".csv"):
            print("Error: --to-yaml requires a CSV input file.", file=sys.stderr)
            sys.exit(1)
        try:
            try:
                import yaml
            except ImportError as e:
                # print error
                print(
                    f"Error: YAML conversion requires 'yaml' package (PyYAML). Please install PyYAML: {e}",
                    file=sys.stderr,
                )
                sys.exit(1)

            model = TaskModel(args.workflow_path)
            model.load_tasks_from_csv()

            steps = model.dynamic_header[2:] if len(model.dynamic_header) > 2 else []
            tasks = []
            for t in model.tasks:
                step_map = {}
                for idx, step_name in enumerate(steps):
                    step = t.steps[idx] if idx < len(t.steps) else None
                    if step and step.command and step.command.strip():
                        step_map[step_name] = step.command
                task_entry = {"name": t.name}
                # Include 'info' or 'description' based on content
                if t.info:
                    if "\n" in t.info:
                        task_entry["description"] = t.info
                    else:
                        task_entry["info"] = t.info
                task_entry["steps"] = step_map
                tasks.append(task_entry)

            data = {"steps": steps, "tasks": tasks}

            out_path = args.to_yaml
            out_dir = os.path.dirname(out_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(
                    data,
                    f,
                    allow_unicode=True,
                    sort_keys=False,
                    default_flow_style=False,
                )
            print(f"YAML written to: {out_path}")
            return  # do not sys.exit(0), avoid SystemExit in tests
        except TaskLoadError as e:
            print(f"Error: Failed to parse CSV: {e}", file=sys.stderr)
            sys.exit(1)
        except OSError as e:
            print(f"Error: Failed to write YAML file: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error: Conversion failed: {e}", file=sys.stderr)
            sys.exit(1)

    # Validate workers count
    if args.workers <= 0:
        print(
            f"Error: Number of workers must be positive, got {args.workers}.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Starting TaskPanel for workflow: {args.workflow_path}")
    print(f"Max workers: {args.workers}")
    print(f"Title: {args.title}")
    print()

    try:
        run(
            workflow_path=args.workflow_path, max_workers=args.workers, title=args.title
        )
    except FileNotFoundError as e:
        print("Error: Could not find the specified workflow file.", file=sys.stderr)
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except TaskLoadError as e:
        print("Error: Failed to load tasks from the workflow file.", file=sys.stderr)
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
