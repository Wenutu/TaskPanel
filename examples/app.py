#!/usr/bin/env python3
"""
Example script demonstrating TaskPanel library usage.
"""
import taskpanel


def main():
    """Run TaskPanel with example tasks."""
    print("Starting TaskPanel with example tasks...")

    try:
        taskpanel.run(csv_path="tasks.csv", max_workers=4, title="Example Workflow")
    except FileNotFoundError as e:
        print(f"Error: Task file not found - {e}")
    except taskpanel.TaskLoadError as e:
        print(f"Error: Failed to load tasks - {e}")
    except KeyboardInterrupt:
        print("Interrupted by user")


if __name__ == "__main__":
    main()
