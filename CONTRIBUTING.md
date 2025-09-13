# Contributing to TaskPanel

Thank you for your interest in contributing to TaskPanel! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.6 or higher
- Git

### Setting Up Development Environment

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Wenutu/TaskPanel.git
   cd TaskPanel
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**:
   ```bash
   make install-dev
   # or manually:
   pip install -e ".[dev]"
   ```

4. **Set up pre-commit hooks**:
   ```bash
   pre-commit install
   ```

## Development Workflow

### Code Style

We use several tools to maintain code quality:

- **Black**: Code formatting
- **isort**: Import sorting  
- **flake8**: Linting
- **mypy**: Type checking

Run all formatting tools:
```bash
make format
```

Check code style:
```bash
make format-check
make lint
```

### Testing

#### Running Tests

```bash
# Run all tests
make test

# Run tests with coverage
make test-cov

# Run tests on all Python versions
make test-all
```

#### Writing Tests

- Place tests in the `tests/` directory
- Use descriptive test names: `test_function_behavior_when_condition`
- Follow the existing test patterns
- Add tests for any new functionality
- Ensure good test coverage

### Making Changes

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**:
   - Write clear, concise code
   - Follow the existing code style
   - Add tests for new functionality
   - Update documentation if needed

3. **Run the development checks**:
   ```bash
   make dev-test
   ```

4. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Add feature: description of your changes"
   ```

5. **Push to your fork and create a pull request**:
   ```bash
   git push origin feature/your-feature-name
   ```

## Pull Request Guidelines

### Before Submitting

- [ ] Tests pass (`make test`)
- [ ] Code follows style guidelines (`make format-check lint`)
- [ ] Documentation is updated if needed
- [ ] Changes are described clearly in the PR description

### PR Description Template

```markdown
## Description
Brief description of the changes.

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] Tests added/updated
- [ ] All tests pass
- [ ] Manual testing performed

## Checklist
- [ ] Code follows the project's style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or clearly documented)
```

## Code Guidelines

### Python Style

- Follow PEP 8
- Use type hints where appropriate
- Write docstrings for public functions and classes
- Keep functions focused and small
- Use meaningful variable and function names

### Documentation

- Update README.md for significant changes
- Add docstrings to new functions and classes
- Update examples if API changes
- Consider adding examples for new features

### Error Handling

- Use appropriate exception types
- Provide helpful error messages
- Handle edge cases gracefully
- Don't suppress exceptions without good reason

## Architecture Guidelines

TaskPanel follows the Model-View-Controller (MVC) pattern:

- **Model** (`model.py`): Data and business logic
- **View** (`view.py`): UI rendering (stateless)
- **Controller** (`runner.py`): Coordination and user input

When making changes:
- Keep the separation of concerns
- Avoid tight coupling between components
- Consider backward compatibility

## Release Process

Releases are handled by maintainers:

1. Version bump in `taskpanel/__init__.py`
2. Update CHANGELOG.md
3. Create git tag
4. GitHub Actions handles PyPI publication

## Getting Help

- Open an issue for bugs or feature requests
- Start a discussion for questions
- Check existing issues before creating new ones

## Code of Conduct

Please be respectful and constructive in all interactions. We're all here to make TaskPanel better!

Thank you for contributing! 🎉
