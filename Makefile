.PHONY: help install install-dev test test-all lint format clean build release docs

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install the package
	pip install -e .

install-dev:  ## Install development dependencies
	@echo "Installing development dependencies..."
	pip install pytest pytest-cov black flake8 mypy bandit safety build twine
	pip install -e .
	@if command -v pre-commit >/dev/null 2>&1; then \
		pre-commit install; \
	else \
		echo "💡 Optional: install pre-commit with 'pip install pre-commit' for git hooks"; \
	fi

test:  ## Run tests
	pytest tests/ -v

test-all:  ## Run tests on all Python versions using tox
	@if command -v tox >/dev/null 2>&1; then \
		tox; \
	else \
		echo "❌ tox not found. Install with: pip install tox"; \
		echo "💡 Running basic tests instead..."; \
		$(MAKE) test; \
	fi

test-cov:  ## Run tests with coverage
	@if python -c "import pytest_cov" 2>/dev/null; then \
		pytest tests/ -v --cov=src/taskpanel --cov-report=html --cov-report=term; \
	else \
		echo "❌ pytest-cov not found. Install with: pip install pytest-cov"; \
		echo "💡 Running tests without coverage..."; \
		pytest tests/ -v; \
	fi

lint:  ## Run all linting tools
	@echo "Running linting tools..."
	@if command -v flake8 >/dev/null 2>&1; then \
		flake8 src/taskpanel tests --ignore=E501,F541,F401,E203,E741,W503 --max-line-length=120; \
	else \
		echo "⚠️  flake8 not found. Install with: pip install flake8"; \
	fi

format:  ## Format code
	@if command -v black >/dev/null 2>&1; then \
		black src/taskpanel tests; \
	else \
		echo "❌ black not found. Install with: pip install black"; \
	fi

format-check:  ## Check code formatting
	@echo "Checking code formatting (relaxed mode)..."
	@if command -v black >/dev/null 2>&1; then \
		black --check --diff --line-length=88 src/taskpanel tests || echo "⚠️ Code formatting could be improved but not enforced"; \
	else \
		echo "❌ black not found. Install with: pip install black"; \
	fi

clean:  ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build:  ## Build package
	python -m build

build-check:  ## Build and check package
	python -m build
	twine check dist/*

release:  ## Build and upload to PyPI (use with caution)
	@echo "This will upload to PyPI. Make sure you're ready!"
	@read -p "Continue? [y/N] " confirm && [[ $$confirm == [yY] ]] || exit 1
	python -m build
	twine check dist/*
	twine upload dist/*

pre-commit:  ## Run pre-commit on all files
	pre-commit run --all-files

# Development shortcuts
dev-setup: install-dev  ## Set up development environment

dev-test: format-check lint test  ## Run all development checks

# CI simulation
ci: format-check lint test build-check  ## Simulate CI checks locally
