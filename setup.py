#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Setup script for TaskPanel package.
"""

from setuptools import setup, find_packages
import os


# Read the long description from README.md
def read_long_description():
    here = os.path.abspath(os.path.dirname(__file__))
    readme_path = os.path.join(here, "README.md")

    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "TaskPanel: A Robust Interactive Terminal Task Runner Library"


# Read version from __init__.py
def read_version():
    here = os.path.abspath(os.path.dirname(__file__))
    init_path = os.path.join(here, "src", "taskpanel", "__init__.py")

    with open(init_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("__version__"):
                # Extract version string
                return line.split("=")[1].strip().strip('"').strip("'")
    return "1.0.0"


setup(
    name="taskpanel",
    version=read_version(),
    author="Wenutu",
    author_email="",
    description="A Robust Interactive Terminal Task Runner Library",
    long_description=read_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/Wenutu/TaskPanel",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Systems Administration",
        "Topic :: Terminals",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: POSIX",
        "Operating System :: MacOS",
        "Operating System :: Unix",
        "Environment :: Console :: Curses",
    ],
    python_requires=">=3.6",
    install_requires=[
        # TaskPanel doesn't require external dependencies
        # It uses only Python standard library
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov",
            "black",
            "flake8",
        ],
    },
    entry_points={
        "console_scripts": [
            "taskpanel=taskpanel.cli:main",
        ],
    },
    package_data={
        "taskpanel": [
            "*.py",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords="terminal task runner workflow parallel execution curses tui",
    project_urls={
        "Bug Reports": "https://github.com/Wenutu/TaskPanel/issues",
        "Source": "https://github.com/Wenutu/TaskPanel",
        "Documentation": "https://github.com/Wenutu/TaskPanel#readme",
    },
)
