# TaskPanel: A Robust Interactive Terminal Task Runner

[![Python Support](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

TaskPanel is a professional-grade, terminal-based tool designed to run, monitor, and manage multi-step parallel tasks defined in a simple CSV file. It provides a highly responsive and fault-tolerant TUI (Text-based User Interface) for complex workflows.

## Key Features

### Core Functionality
- **Parallel Execution**: Runs each task (row in the CSV) in a parallel worker thread
- **Sequential Steps**: Executes the steps (columns) within each task sequentially
- **Interactive TUI**: A full-screen, responsive `curses`-based interface to monitor task status
- **Detailed Views**: Context-aware panels show task information and step output
- **Advanced Navigation**: 
  - Vertical scrolling for hundreds of tasks
  - Horizontal scrolling for tasks with many steps

### Robustness & Reliability
- **State Persistence**: Intelligent resume capability after crashes or interruptions
- **Task State Management**: Completed tasks preserved, interrupted tasks reset appropriately
- **Concurrency Control**: Configurable worker limits to prevent resource exhaustion
- **Safe Threading**: Deadlock-free threading with proper synchronization

### Performance & Debugging
- **Log Management**: Structured logging with unique directories per task
- **Efficient UI**: Smart refresh mechanism for minimal CPU usage
- **Debug Features**: Toggleable debug panel with detailed lifecycle information

### New
- **YAML Workflow Support**: Load workflows from YAML files with strict schema validation
- **CSV → YAML Conversion**: Convert CSV workflows to YAML via CLI (requires PyYAML)

## Installation

```bash
pip install taskpanel
```

or from source:

```bash
git clone https://github.com/Wenutu/TaskPanel.git
cd TaskPanel
pip install -e .
```

> Note: UI runtime requires a POSIX-like OS (Linux/macOS).

#### Quick Start

1. Define your workflow
   - CSV:
     ```csv
     TaskName,Info,Checkout,Build,Test
     MyApp,v1.0.0,./scripts/1_checkout.sh,./scripts/2_build.sh,./scripts/3_test.sh
     ```
   - YAML:
     ```yaml
     steps: [Checkout, Build, Test]
     tasks:
       - name: MyApp
         info: v1.0.0
         steps:
           Checkout: "./scripts/1_checkout.sh"
           Build: "./scripts/2_build.sh"
           Test: "./scripts/3_test.sh"
     ```

2. Run from command line
   ```bash
   # CSV
   taskpanel tasks.csv

   # YAML
   taskpanel tasks.yaml
   ```

3. Or use as a Python library
   ```python
   import taskpanel

   taskpanel.run(
       workflow_path="tasks.csv",  # or "tasks.yaml"
       max_workers=4,
       title="My Workflow"
   )
   ```

#### Example Project Structure

```
your_project/
├── tasks.csv         # or tasks.yaml
├── scripts/
│   ├── 1_checkout.sh
│   ├── 2_build.sh
│   ├── 3_test.sh
│   └── 4_deploy.sh
└── app.py
```

## Task Definition Format

Define your workflow using CSV or YAML. In both formats, each task has sequential steps.

### CSV
- Header row with at least: TaskName, Info
- Subsequent columns are step names; each cell is a shell command (empty means no step)

Example:
```csv
TaskName,Info,Checkout,Build,Test,Deploy
WebApp,v1.2.0,./scripts/1_checkout.sh,./scripts/2_build.sh,./scripts/3_test.sh,./scripts/4_deploy.sh
API-Server,v1.2.0,./scripts/1_checkout.sh,./scripts/2_build.sh --api,./scripts/3_test.sh --integration,./scripts/4_deploy.sh --api
```

### YAML (strict schema)
Top-level keys:
- steps: optional list of step names
- tasks: required list of task objects

Each task:
- name: string (required)
- info or description: string (optional; use description for multiline)
- steps: mapping of step_name (string) to command (string, nullable)

Example:
```yaml
steps: [Checkout, Build, Test, Deploy]  # optional; will be derived if omitted
tasks:
  - name: WebApp
    info: v1.2.0
    steps:
      Checkout: "./scripts/1_checkout.sh"
      Build: "./scripts/2_build.sh"
      Test: "./scripts/3_test.sh"
      Deploy: "./scripts/4_deploy.sh"
  - name: API-Server
    description: |
      Version: v1.2.0
      Owner: Bob
    steps:
      Checkout: "./scripts/1_checkout.sh"
      Build: "./scripts/2_build.sh --api"
      Test: "./scripts/3_test.sh --integration"
      Deploy: "./scripts/4_deploy.sh --api"
```

Validation rules:
- Only top-level keys steps and tasks are allowed
- Only task keys name, info, description, steps are allowed
- steps mapping must have string keys and string or null values

Notes (YAML specifics):
- If top-level steps is omitted, TaskPanel derives the step headers in the order of first appearance across tasks. For stable ordering across runs and clearer UI, it is recommended to define steps explicitly at the top level.
- A step command can be null or empty per task; it effectively removes the step for that task while the step name can still appear in the top-level steps.
- PyYAML is required for YAML parsing and CSV→YAML conversion: pip install pyyaml

## Usage

### Command Line Interface

```bash
# Basic usage (CSV or YAML)
taskpanel tasks.csv
taskpanel tasks.yaml

# Options
taskpanel tasks.csv --workers 8 --title "My Build Pipeline"

# Convert CSV to YAML (requires PyYAML)
taskpanel tasks.csv --to-yaml tasks.yaml
```

--to-yaml notes:
- Input must be a CSV file
- Output YAML contains only steps and tasks at top level
- Single-line Info becomes info; multiline Info becomes description
- Empty step cells are omitted from a task’s steps mapping (still listed in top-level steps)
- Conversion preserves the header order; for consistent visual order in YAML-only workflows, consider providing a top-level steps list

### Python Library

```python
#!/usr/bin/env python3
import taskpanel

def main():
    try:
        taskpanel.run(
            workflow_path="tasks.csv",  # or "tasks.yaml"
            max_workers=4,
            title="My Workflow Runner"
        )
    except FileNotFoundError as e:
        print(f"Error: Task file not found - {e}")
    except KeyboardInterrupt:
        print("Interrupted by user")

if __name__ == "__main__":
    main()
```

### Interactive Controls

| Key | Action |
|-----|--------|
| ↑ ↓ | Navigate tasks |
| ← → | Navigate columns |
| Home / End | Jump to first/last task |
| PgUp / PgDn | Page scroll |
| r | Rerun selected step and subsequent steps |
| k | Kill currently running task |
| d | Toggle debug panel |
| [ / ] | Scroll output log |
| { / } | Scroll debug log |
| q | Quit |

## Project Architecture

- Model (`src/taskpanel/model.py`): Task execution, state management, persistence
- View (`src/taskpanel/view.py`): Terminal UI rendering with curses
- Controller (`src/taskpanel/runner.py`): Event loop and user input handling
- CLI (`src/taskpanel/cli.py`): Command-line interface

## Development

```bash
git clone https://github.com/Wenutu/TaskPanel.git
cd TaskPanel
pip install -e ".[dev]"
# or
make install-dev
```

### Make Commands

- `make test` - Run tests
- `make lint` - Run linting tools
- `make format` - Format code
- `make build` - Build package
- `make clean` - Clean build artifacts

## Compatibility

- OS: POSIX-like only (Linux, macOS)
- YAML: Parsing and conversion require PyYAML (`pip install pyyaml`)

## Troubleshooting

Common issues and tips:
- Workflow file not found
  - Ensure the path is correct. TaskPanel accepts .csv, .yaml, .yml. Check your current working directory.
- YAML load errors
  - Only top-level keys steps and tasks are allowed.
  - Each task allows only name, info/description, steps.
  - Ensure PyYAML is installed: pip install pyyaml
- CSV load errors
  - Header must include at least TaskName and Info.
  - Empty rows are ignored; ensure step columns align with your header.
- Unexpected step order in YAML
  - If top-level steps is omitted, order is derived by first appearance across tasks. Provide steps at top-level to lock order.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Links
- [PyPI Package](https://pypi.org/project/taskpanel/)
- [GitHub Repository](https://github.com/Wenutu/TaskPanel)
- [Latest Release](https://github.com/Wenutu/TaskPanel/releases/latest)
- [Download Packages](https://github.com/Wenutu/TaskPanel/releases)
- [Documentation](https://github.com/Wenutu/TaskPanel#readme)
- [Issues](https://github.com/Wenutu/TaskPanel/issues)
