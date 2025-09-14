# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2025-09-14

### Changed
- **BREAKING**: Migrated to src/ layout package structure
- Simplified test suite focused on packaging validation
- Updated all configuration files for new src/ structure
- Streamlined documentation and examples
- Removed complex integration tests in favor of simple unit tests

### Added
- Modern Python packaging structure with src/ layout
- Simplified test suite for better CI/CD compatibility
- Updated documentation reflecting new project structure

### Removed
- Complex curses-based integration tests (incompatible with CI environments)
- Redundant test files and dependencies

## [1.0.0] - 2025-09-13

### Added
- Initial release of TaskPanel
- Interactive terminal-based task runner
- CSV-based task definition format
- Parallel task execution with configurable worker limits
- Intelligent state persistence and resume functionality
- Real-time task monitoring with curses-based TUI
- Command-line interface
- Python library API
- Model-View-Controller architecture
- Comprehensive error handling and logging
- Example scripts and tasks

### Features
- **Parallel Execution**: Run multiple tasks simultaneously with worker limits
- **Sequential Steps**: Execute steps within each task in sequence
- **State Persistence**: Automatically save and restore task state
- **Interactive Controls**: Navigate, rerun, and kill tasks via keyboard
- **Debug Panel**: Detailed logging and process information
- **Cross-platform**: Works on Linux and macOS with Python 3.6+

### Documentation
- Comprehensive README with usage examples
- API documentation and architecture overview
- Example configurations and scripts
