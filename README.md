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

## Installation

```bash
pip install taskpanel
```

或从源码安装：

```bash
git clone https://github.com/Wenutu/TaskPanel.git
cd TaskPanel
pip install -e .
```

#### Quick Start

1. **Create your task definition file** (`tasks.csv`):
   ```csv
   TaskName,Info,Checkout,Build,Test
   MyApp,v1.0.0,./scripts/1_checkout.sh,./scripts/2_build.sh,./scripts/3_test.sh
   ```

2. **Run from command line**:
   ```bash
   taskpanel tasks.csv
   ```

3. **Or use as a Python library**:
   ```python
   import taskpanel
   
   taskpanel.run(
       csv_path="tasks.csv",
       max_workers=4,
       title="My Workflow"
   )
   ```

#### Example Project Structure

```
your_project/
├── tasks.csv         # Task definitions
├── scripts/          # Your workflow scripts
│   ├── 1_checkout.sh
│   ├── 2_build.sh
│   ├── 3_test.sh
│   └── 4_deploy.sh
└── app.py           # Your main application (optional)
```

## Task Definition Format

Define your workflow in a CSV file with the **first row as headers**.

**Format**: `TaskName,Info,Step1Header,Step2Header,...`

**Example `tasks.csv`:**
```csv
TaskName,Info,Checkout,Build,Test,Deploy
WebApp,v1.2.0,./scripts/1_checkout.sh,./scripts/2_build.sh,./scripts/3_test.sh,./scripts/4_deploy.sh
API-Server,v1.2.0,./scripts/1_checkout.sh,./scripts/2_build.sh --api,./scripts/3_test.sh --integration,./scripts/4_deploy.sh --api
```

Each task (row) will be executed as a pipeline where steps run sequentially.

## Usage

### Command Line Interface

```bash
# Basic usage
taskpanel tasks.csv

# With options
taskpanel tasks.csv --workers 8 --title "My Build Pipeline"

# Show help
taskpanel --help
```

### Python Library

```python
#!/usr/bin/env python3
import taskpanel

def main():
    try:
        taskpanel.run(
            csv_path="tasks.csv",
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
| `↑` `↓` | Navigate between tasks |
| `←` `→` | Navigate between columns |
| `Home` / `End` | Jump to first/last task |
| `PgUp` / `PgDn` | Scroll by page |
| `r` | **Rerun** selected step and subsequent steps |
| `k` | **Kill** currently running task |
| `d` | Toggle debug panel |
| `[` / `]` | Scroll output log |
| `{` / `}` | Scroll debug log |
| `q` | **Quit** application |

## Project Architecture

TaskPanel follows a clean Model-View-Controller (MVC) architecture:

- **Model (`src/taskpanel/model.py`)**: Task execution, state management, and persistence
- **View (`src/taskpanel/view.py`)**: Terminal UI rendering with curses
- **Controller (`src/taskpanel/runner.py`)**: Event loop and user input handling
- **CLI (`src/taskpanel/cli.py`)**: Command-line interface

This separation ensures maintainability and testability.

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/Wenutu/TaskPanel.git
cd TaskPanel

# Install in development mode
pip install -e ".[dev]"

# Or use make
make install-dev
```

### Project Structure

```
TaskPanel/
├── src/
│   └── taskpanel/         # Main package
│       ├── __init__.py    # Package entry point
│       ├── cli.py         # Command-line interface
│       ├── model.py       # Task execution logic
│       ├── runner.py      # Main controller
│       └── view.py        # Terminal UI
├── tests/                 # Test suite
├── scripts/               # Example scripts
├── pyproject.toml         # Build configuration
├── Makefile              # Development commands
└── README.md             # This file
```

### Make Commands

- `make test` - Run tests
- `make lint` - Run linting tools
- `make format` - Format code
- `make build` - Build package
- `make clean` - Clean build artifacts

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Run tests: `make test`
5. Submit a pull request

Please ensure your code follows the project style and includes appropriate tests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Links

## Links

- [PyPI Package](https://pypi.org/project/taskpanel/)
- [GitHub Repository](https://github.com/Wenutu/TaskPanel)
- [Latest Release](https://github.com/Wenutu/TaskPanel/releases/latest)
- [Download Packages](https://github.com/Wenutu/TaskPanel/releases)
- [Documentation](https://github.com/Wenutu/TaskPanel#readme)
- [Issues](https://github.com/Wenutu/TaskPanel/issues)
