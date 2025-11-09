import os
from pathlib import Path

def initialize_project_environment():
    """
    Sets up the basic project structure for a full-stack application.
    This script creates directories and empty files as defined in the project structure.
    """
    project_root = Path("project")

    # Define all directories to be created
    directories = [
        project_root / "backend" / "src",
        project_root / "backend" / "src" / "api",
        project_root / "backend" / "src" / "api" / "v1",
        project_root / "backend" / "src" / "config",
        project_root / "backend" / "src" / "core",
        project_root / "backend" / "src" / "db",
        project_root / "backend" / "src" / "schemas",
        project_root / "backend" / "src" / "services",
        project_root / "backend" / "tests",
        project_root / "frontend" / "public",
        project_root / "frontend" / "src",
        project_root / "frontend" / "src" / "assets",
    ]

    # Define all files to be created (as empty files)
    files = [
        project_root / "backend" / "src" / "__init__.py",
        project_root / "backend" / "src" / "main.py",
        project_root / "backend" / "src" / "api" / "__init__.py",
        project_root / "backend" / "src" / "api" / "v1" / "__init__.py",
        project_root / "backend" / "src" / "api" / "v1" / "health.py",
        project_root / "backend" / "src" / "config" / "__init__.py",
        project_root / "backend" / "src" / "config" / "settings.py",
        project_root / "backend" / "src" / "core" / "__init__.py",
        project_root / "backend" / "src" / "core" / "exceptions.py",
        project_root / "backend" / "src" / "core" / "security.py",
        project_root / "backend" / "src" / "db" / "__init__.py",
        project_root / "backend" / "src" / "db" / "database.py",
        project_root / "backend" / "src" / "schemas" / "__init__.py",
        project_root / "backend" / "src" / "schemas" / "health.py",
        project_root / "backend" / "src" / "services" / "__init__.py",
        project_root / "backend" / "tests" / "__init__.py",
        project_root / "backend" / "tests" / "test_api.py",
        project_root / "backend" / ".env.example",
        project_root / "backend" / "Dockerfile",
        project_root / "backend" / "requirements.txt",
        project_root / "backend" / "README.md",
        project_root / "frontend" / "src" / "App.css",
        project_root / "frontend" / "src" / "App.jsx",
        project_root / "frontend" / "src" / "main.jsx",
        project_root / "frontend" / ".env.example",
        project_root / "frontend" / ".eslintrc.cjs",
        project_root / "frontend" / "index.html",
        project_root / "frontend" / "package.json",
        project_root / "frontend" / "postcss.config.js",
        project_root / "frontend" / "tailwind.config.js",
        project_root / "frontend" / "vite.config.js",
        project_root / "frontend" / "README.md",
        project_root / ".dockerignore",
        project_root / ".gitignore",
        project_root / "docker-compose.yml",
        project_root / "README.md",
    ]

    print(f"Initializing project structure under '{project_root.resolve()}'...")

    # Create all defined directories
    for directory in directories:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"Created directory: {directory}")
        except OSError as e:
            print(f"Error creating directory {directory}: {e}")
            # Depending on the severity, you might want to raise the exception
            # or exit the script here. For now, we just print the error.

    # Create all defined empty files
    for file_path in files:
        try:
            file_path.touch(exist_ok=True)
            print(f"Created file: {file_path}")
        except OSError as e:
            print(f"Error creating file {file_path}: {e}")
            # Similar error handling as for directories.

    print("Project environment initialized successfully.")

if __name__ == "__main__":
    initialize_project_environment()