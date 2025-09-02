# TaskPanel: A Robust Interactive Terminal Task Runner Library

TaskPanel is a professional-grade, terminal-based tool, packaged as a Python library, designed to run, monitor, and manage multi-step parallel tasks defined in a simple CSV file. By calling a single function, you can launch a highly responsive and fault-tolerant TUI (Text-based User Interface) for your complex workflows.

It excels at managing long-running processes by offering features like intelligent state persistence, concurrency control, and detailed, real-time feedback without overwhelming system resources.

## Key Features

TaskPanel was engineered for stability and professional use. Its features are built on a foundation of robust error handling and concurrent programming best practices.

#### Core Functionality
*   **Parallel Execution**: Runs each task (row in the CSV) in a parallel worker thread.
*   **Sequential Steps**: Executes the steps (columns) within each task sequentially.
*   **Interactive TUI**: A full-screen, responsive `curses`-based interface to monitor the status of every step.
*   **Detailed Views**: A context-aware panel shows the full, multi-line `Info` for a task or the `STDOUT`/`STDERR` for a specific step.
*   **Advanced Navigation**:
    *   **Vertical Scrolling**: Seamlessly handles hundreds of tasks using `Up`/`Down`, `PgUp`/`PgDn`, `Home`/`End`.
    *   **Horizontal Scrolling**: Manages tasks with dozens of steps using `Left`/`Right` arrows to scroll the view.

#### Unmatched Robustness & Reliability
*   **Intelligent Resume on Crash**: If the application is interrupted, it intelligently resumes upon restart.
    *   **Completed tasks** (SUCCESS, FAILED) are preserved.
    *   **Interrupted tasks** (RUNNING, KILLED) are precisely reset from the point of failure, preserving all prior successful steps.
*   **State Integrity Guarantee**:
    *   Task state is saved to a JSON file (e.g., `.tasks.csv.state.json`).
    *   A **SHA256 hash of each task's command structure** is stored. If a task's commands are modified, TaskPanel automatically invalidates only that task's state to prevent errors, while preserving the state of unchanged tasks.
    *   State file writes are **atomic**, preventing corruption even if the application is killed during a save.
*   **Concurrency Control**: The `max_workers` parameter in the `run()` function limits the number of concurrently running tasks, preventing system resource exhaustion.
*   **Deadlock-Free Threading**: Employs a robust `run_counter` mechanism and `RLock` to manage thread ownership, ensuring that rapid `rerun` or `kill` commands are handled safely without race conditions.

#### Performance & Debugging
*   **Stable Log Archiving**: `stdout` and `stderr` for each step are streamed to unique, stable log directories based on the task's unique ID (e.g., `.logs/WebApp-Build_a1b2c3d4/`). This path **does not change** if you reorder rows in the CSV.
*   **Smart UI Refresh**: The UI only redraws when a state changes or on a gentle timer, ensuring minimal CPU usage when idle.
*   **Contextual Debug Panel**: A toggleable (`d` key) panel shows detailed, step-specific lifecycle logs, including user actions, process PIDs, and timings.

## Installation & Setup

TaskPanel is designed to run on POSIX-like systems (Linux, macOS) with Python 3.6+.

#### 1. Prerequisites
- Python 3.6+
- A terminal with `curses` support.

No external libraries are required.

#### 2. File Structure
To use TaskPanel as a library, organize your project as follows:

```
your_project/
├── taskpanel/
│   ├── __init__.py
│   ├── model.py
│   ├── view.py
│   └── runner.py
├── my_app.py         # Your script that will run the TaskPanel
├── tasks.csv
└── scripts/
    ├── build.sh
    └── deploy.sh
```

#### 3. Prepare your `tasks.csv`
The CSV file defines your workflow. The **first row must be a header row**.

**Format**: `TaskName,Info,Step1Header,Step2Header,...`

**Example `tasks.csv`:**
```csv
TaskName,Info,Checkout,Build,Test
WebApp-Build,v1.2-main,./scripts/checkout.sh,./scripts/build.sh --target web,./scripts/test.sh
API-Server,v1.2-main,./scripts/checkout.sh,./scripts/build.sh --target api,./scripts/test.sh --integration
Legacy-Tool,rev-2023-q4,"A long, multi-line description.",./scripts/run_legacy.sh
```

## Usage (as a Library)

To use TaskPanel, import it into your Python script and call the `run()` function with your desired configuration.

**Example `my_app.py`:**
```python
#!/usr/bin/env python3
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
        taskpanel.run(
            csv_path=CSV_FILE,
            max_workers=MAX_WORKERS,
            title=APP_TITLE
        )
    except FileNotFoundError as e:
        print(f"ERROR: Could not find the specified CSV file.")
        print(e)
    except taskpanel.TaskLoadError as e:
        print(f"ERROR: Failed to load tasks from the CSV file.")
        print(e)
    except OSError as e:
        print(f"Operating System Error: {e}")
    except KeyboardInterrupt:
        # taskpanel.run handles this gracefully, but you can add custom logic here.
        print("Application was interrupted by the user.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
```

### Interactive Controls

| Key           | Action                                        |
|---------------|-----------------------------------------------|
| `↑` `↓`         | Navigate between tasks (rows).                |
| `←` `→`         | Navigate between Info and Step columns.       |
| `Home` / `End`  | Jump to the first / last task.                |
| `PgUp` / `PgDn` | Scroll the task list up / down by a full page.|
| `r`             | **Rerun** the selected step and all subsequent steps for that task. |
| `k`             | **Kill** the currently running task row.      |
| `d`             | Toggle the contextual **Debug Panel**.        |
| `[` / `]`         | Scroll the Output Log panel up / down.        |
| `{` / `}`         | Scroll the Debug Log panel up / down.         |
| `q`             | **Quit** the application, saving state.       |

## Architecture: Model-View-Controller (MVC)

TaskPanel is built using a clean MVC architecture to ensure maintainability and separation of concerns.

*   **Model (`model.py`)**: Contains all data and business logic. It handles task execution, state changes, and persistence.
*   **View (`view.py`)**: Responsible for all `curses`-based rendering. It is stateless and simply draws the data provided to it.
*   **Controller (`runner.py`)**: The central hub. It orchestrates the Model and View, runs the main event loop, and handles user input.

## Contributing

Contributions are welcome! Please feel free to open an issue to report a bug or suggest a feature, or submit a pull request with your improvements.

## License

This project is licensed under the MIT License.
