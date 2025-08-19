# TaskPanel: A Robust Interactive Terminal Task Runner

TaskPanel is a professional-grade, terminal-based tool designed to run, monitor, and manage multi-step parallel tasks defined in a simple CSV file. Built with a robust Model-View-Controller (MVC) architecture in Python, it provides a highly responsive and fault-tolerant TUI (Text-based User Interface) for complex workflows, especially in environments like HPC clusters or CI/CD pipelines.

 
It excels at managing long-running processes by offering features like intelligent state persistence, concurrency control, and detailed, real-time feedback without overwhelming system resources.

## Key Features

TaskPanel was engineered for stability and professional use. Its features are built on a foundation of robust error handling and concurrent programming best practices.

#### Core Functionality
*   **Parallel Execution**: Runs each task (row in the CSV) in a parallel worker thread.
*   **Sequential Steps**: Executes the steps (columns) within each task sequentially.
*   **Interactive TUI**: A full-screen, responsive `curses`-based interface to monitor the status of every step.
*   **Detailed Views**: A context-aware panel shows the full, multi-line `Info` for a task or the `STDOUT`/`STDERR` for a specific step.
*   **Advanced Navigation**:
    *   **Vertical Scrolling**: Seamlessly handles hundreds or thousands of tasks using `Up`/`Down`, `PgUp`/`PgDn`, `Home`/`End`.
    *   **Horizontal Scrolling**: Manages tasks with dozens of steps using `Left`/`Right` arrows to scroll the view.

#### Unmatched Robustness & Reliability
*   **Intelligent Resume on Crash**: If the application is interrupted, it intelligently resumes upon restart.
    *   **Completed tasks** (SUCCESS, FAILED) are preserved.
    *   **Interrupted tasks** (RUNNING, KILLED) are precisely reset from the point of failure, preserving all prior successful steps.
*   **State Integrity Guarantee**:
    *   Task state is saved to a JSON file (`.tasks.csv.state.json`).
    *   A **SHA256 hash** of the source CSV is stored in the state file. If the CSV is modified in any way, TaskPanel automatically invalidates the old state to prevent data corruption and starts fresh.
    *   State file writes are **atomic**, preventing corruption even if the application is killed during a save.
*   **Concurrency Control**: Uses a `ThreadPoolExecutor` to limit the number of concurrently running tasks (`--max-workers` flag), preventing system resource exhaustion with large CSV files.
*   **Deadlock-Free Threading**: Employs a robust `run_counter` mechanism and `RLock` to manage thread ownership, ensuring that rapid `rerun` or `kill` commands are handled safely without race conditions or deadlocks.

#### Performance & Debugging
*   **High-Performance Log Archiving**: `stdout` and `stderr` for each step are streamed directly to unique log files (`.logs/001-TaskName-Info/step-01.log`). This prevents memory overflow from tasks with massive output.
*   **Smart UI Refresh**: The UI only redraws when a state changes or the user provides input, ensuring minimal CPU usage when idle.
*   **Contextual Debug Panel**: A toggleable (`d` key) panel shows detailed, step-specific lifecycle logs, including user actions (`rerun`, `kill`), process PIDs, and execution timings.

## Installation & Setup

TaskPanel is designed to run on POSIX-like systems (Linux, macOS) with Python 3.6+.

#### 1. Prerequisites
- Python 3.6+
- A terminal with `curses` support.

No external libraries are required.

#### 2. File Structure
Organize your project as follows:

```
task_runner/
├── runner.py             # Main executable (Controller)
├── model.py              # Data and business logic (Model)
├── view.py               # TUI rendering (View)
├── tasks.csv             # Your task definitions
└── scripts/
    ├── build.sh
    └── deploy.sh
```

#### 3. Prepare your `tasks.csv`
The CSV file defines your workflow. It does not use a header row.

**Format**: `TaskName, Info, Command1, Command2, ...`

*   **TaskName**: A unique name or identifier for the task.
*   **Info**: A short description, version number, or other metadata. Displayed in its own column.
*   **Command1, Command2, ...**: The shell commands to be executed sequentially.

**Example `tasks.csv`:**
```csv
WebApp-Build,v1.2-main,./scripts/checkout.sh,./scripts/build.sh --target web,./scripts/test.sh
API-Server,v1.2-main,./scripts/checkout.sh,./scripts/build.sh --target api,./scripts/test.sh --integration
Legacy-Tool,rev-2023-q4,"A long, multi-line description of this legacy process.
It is important to monitor its output.",./scripts/run_legacy.sh
```

## Usage

Navigate to the `task_runner` directory and run the main controller script.

#### Basic Execution
To run with the default `tasks.csv` and a worker pool sized to your CPU count:
```bash
python runner.py
```

#### Specifying a CSV and Worker Count
```bash
python runner.py /path/to/my_workflow.csv --max-workers 8
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

*   **Model (`model.py`)**: Contains all data (`tasks` list) and business logic. It handles task execution, state changes, and persistence. It has no knowledge of the UI.
*   **View (`view.py`)**: Responsible for all `curses`-based rendering. It is stateless and simply draws the data provided to it by the Controller.
*   **Controller (`runner.py`)**: The central hub. It initializes the Model and View, runs the main event loop, handles all user input, calls methods on the Model to update state, and tells the View when to redraw.

## Contributing

Contributions are welcome! Please feel free to open an issue to report a bug or suggest a feature, or submit a pull request with your improvements.

## License

This project is licensed under the [MIT License](LICENSE).

