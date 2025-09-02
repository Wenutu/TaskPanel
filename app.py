#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
An example script demonstrating how to use the TaskPanel library.
"""
import os
import taskpanel

# --- Configuration ---
CSV_FILE = "tasks.csv"
MAX_WORKERS = os.cpu_count() or 4
APP_TITLE = "My Company's Workflow Runner"


def main():
    """Main function to configure and run TaskPanel."""
    print(f"Starting TaskPanel for workflow: {CSV_FILE}")

    try:
        taskpanel.run(csv_path=CSV_FILE, max_workers=MAX_WORKERS, title=APP_TITLE)
    except FileNotFoundError as e:
        print(f"Error: Could not find the specified CSV file.")
        print(e)
    except taskpanel.TaskLoadError as e:
        print(f"Error: Failed to load tasks from the CSV file.")
        print(e)
    except OSError as e:
        print(f"Operating System Error: {e}")
    except KeyboardInterrupt:
        # This is already handled gracefully inside taskpanel.run,
        # but you can add custom cleanup here if needed.
        print("Application was interrupted by the user.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
