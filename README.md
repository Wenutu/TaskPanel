# TaskPanel

**TaskPanel** is a robust, interactive, terminal-based dashboard for running and monitoring multi-step tasks defined in a simple CSV file. It's designed for workflows in bioinformatics, data processing, and HPC environments where you need to execute a series of commands for many items and visually track their progress.


*(This is a representative GIF. You can replace this with an actual screenshot or recording of your tool in action.)*

---

## Core Features

*   **Interactive Terminal UI**: A clean, responsive `curses`-based interface to navigate tasks, view statuses, and inspect outputs without leaving your terminal.
*   **Simple CSV-based Task Definition**: Define complex, multi-step workflows in a plain CSV file. Each row is a task, and each column after the first two is a command step.
*   **Concurrent Task Execution**: Run multiple tasks in parallel using a configurable thread pool to maximize the use of your system's resources.
*   **Robust State Persistence**: The application automatically saves its state upon exit. If you stop and restart it, it seamlessly resumes from where it left off.
*   **Data Integrity Checks**: State is only resumed if the task file hasn't changed (verified via a SHA256 checksum), preventing inconsistent states.
*   **In-flight Task Control**: Interactively **kill** a running task row or **rerun** a task from any specific step, even if it has failed or is still running.
*   **Detailed Output & Debug Views**: Instantly view the `stdout` and `stderr` for any selected step. A toggleable debug panel provides deeper insight into the runner's internal operations for each step.
*   **Clean Process Management**: Uses process groups to ensure that when a task is killed, its entire process tree is terminated, leaving no orphaned processes behind.

## Prerequisites

*   **OS**: A POSIX-compliant operating system (Linux, macOS, etc.).
*   **Python**: Python 3.6+

## Installation & Usage

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd TaskPanel
    ```

2.  **Create a tasks file:**
    Create a `tasks.csv` file in the directory. The format is simple:
    *   **Column 1**: A unique name for the task (e.g., a sample ID).
    *   **Column 2**: A short, descriptive piece of information (optional).
    *   **Column 3 onwards**: The shell commands to be executed in sequence for that task.

    **Example `tasks.csv`:**
    ```csv
    Sample_A,ControlGroup,"echo 'Starting A'; sleep 2; script_align.sh A.fastq", "echo 'Analyzing A'; script_analyze.sh A.bam", "echo 'Done A'; date > A.done"
    Sample_B,TreatmentGroup,"echo 'Starting B'; sleep 2; script_align.sh B.fastq", "echo 'Analyzing B'; script_analyze.sh B.bam", "echo 'Done B'; date > B.done"
    Sample_C,ControlGroup,"echo 'Starting C'; sleep 2; script_align.sh C.fastq", "echo 'Analyzing C'; script_analyze.sh C.bam", "echo 'Done C'; date > C.done"
    Sample_D,FailedCase,"echo 'This will fail'; sleep 1; exit 1", "echo 'This will be skipped'", "echo 'This will also be skipped'"
    ```

3.  **Run the application:**
    ```bash
    python3 runner.py
    ```
    By default, it looks for `tasks.csv` and uses a number of parallel workers equal to your CPU cores.

    You can specify a different CSV file and set the number of workers:
    ```bash
    python3 runner.py /path/to/my_pipeline.csv --max-workers 8
    ```

## Controls

Navigate the dashboard using your keyboard:

| Key(s)                  | Action                                            |
| ----------------------- | ------------------------------------------------- |
| `↑` `↓` `←` `→`         | Navigate the task grid.                           |
| `PgUp` / `PgDn`         | Scroll the task list up or down by a full page.   |
| `Home` / `End`          | Jump to the first or last task.                   |
| `r`                     | **Rerun** the currently selected task from the currently selected step. |
| `k`                     | **Kill** the entire row for the currently selected task. |
| `d`                     | Toggle the **Debug Panel** at the bottom of the screen. |
| `q`                     | **Quit** the application (safely saves state).    |

## How It Works: The MVC Architecture

TaskPanel is built on a classic **Model-View-Controller (MVC)** architecture, which separates concerns and makes the codebase clean and maintainable.

*   **`model.py` (The Model)**
    *   The "brain" of the application. It manages all data and business logic.
    *   It knows nothing about the UI.
    *   **Responsibilities**: Loading tasks from CSV, managing the state of every step (`PENDING`, `RUNNING`, `SUCCESS`, etc.), executing commands in subprocesses, handling state persistence (saving/loading), and ensuring thread safety with locks.

*   **`view.py` (The View)**
    *   The "face" of the application. Its only job is to present data from the Model to the user.
    *   **Responsibilities**: Rendering the entire terminal UI with `curses`, applying colors for different statuses, drawing the task grid, and displaying output/debug logs. It reads data from the model but never modifies it.

*   **`runner.py` (The Controller)**
    *   The "conductor" that connects the Model and the View.
    *   **Responsibilities**: Initializing the application, handling all user input (keyboard presses), and translating those inputs into actions. For example, when you press `r`, the Controller tells the Model to rerun a task. It also manages the main application loop, telling the View to redraw itself periodically.

### Key Design Choices

*   **Concurrency Safety**: A `ThreadPoolExecutor` runs tasks in parallel. All access to shared task data in the Model is protected by a `threading.RLock` to prevent race conditions. The `run_counter` mechanism cleverly prevents "zombie" threads from overwriting the state of a task that has been rerun by the user.
*   **Robust Process Killing**: By using `os.setsid`, each step is run in its own process group. When a task is killed via the UI, `os.killpg` is used to terminate the entire group, ensuring no child processes are left orphaned.
*   **Stateful Resumption**: The state file (`.tasks.csv.state.json`) stores the status of each step. The SHA256 hash of the source CSV is also stored. On startup, if the CSV has been modified, the old state is discarded to prevent errors, forcing a fresh start. Interrupted (`RUNNING` or `KILLED`) tasks are automatically reset to `PENDING`.

## Contributing

Contributions are welcome! Please feel free to open an issue to report a bug or suggest a feature, or submit a pull request with your improvements.

## License

This project is licensed under the [MIT License](LICENSE).

