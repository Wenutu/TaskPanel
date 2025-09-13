# TaskPanel Examples

This directory contains example files and scripts to help you get started with TaskPanel.

## Files

- `app.py` - Example application showing how to use TaskPanel as a library
- `tasks.csv` - Sample task definition file with multiple build/test workflows
- `scripts/` - Example shell scripts referenced by the tasks.csv file

## Quick Start

1. **Install TaskPanel** (if not already installed):
   ```bash
   pip install taskpanel
   ```

2. **Run the example**:
   ```bash
   cd examples
   python app.py
   ```

   Or using the CLI:
   ```bash
   cd examples
   taskpanel tasks.csv
   ```

## Understanding the Example

### tasks.csv Format

The CSV file defines your workflow with the following structure:
- **First row**: Header row (TaskName, Info, Step1, Step2, ...)
- **Subsequent rows**: Task definitions

Example:
```csv
TaskName,Info,Checkout,Build,Test,Deploy
WebApp-Build,v1.2-main,./scripts/1_checkout.sh,./scripts/2_build.sh,./scripts/3_test.sh,./scripts/4_deploy.sh
API-Server,v1.2-main,./scripts/1_checkout.sh,./scripts/2_build.sh --target api,./scripts/3_test.sh --integration,./scripts/4_deploy.sh --api
```

### Script Files

The `scripts/` directory contains example shell scripts:
- `1_checkout.sh` - Simulates source code checkout
- `2_build.sh` - Simulates build process
- `3_test.sh` - Simulates testing
- `4_deploy.sh` - Simulates deployment

These scripts are designed to demonstrate TaskPanel's capabilities with realistic timing and output.

## Customizing for Your Project

1. **Create your own tasks.csv** - Define your actual workflow steps
2. **Create your scripts** - Replace example scripts with your real build/test/deploy commands
3. **Modify app.py** - Adjust settings like max_workers and title for your needs

## Interactive Controls

When running TaskPanel:

| Key | Action |
|-----|--------|
| `↑↓` | Navigate between tasks |
| `←→` | Navigate between columns |
| `r` | Rerun selected step and subsequent steps |
| `k` | Kill running task |
| `d` | Toggle debug panel |
| `q` | Quit application |
