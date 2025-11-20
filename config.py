# config.py
from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Use the current working directory's generated_code folder for Windows compatibility
# This will create the generated_code folder in your project directory
GENERATED_CODE_ROOT = Path.cwd() / "generated_code"

# DEV_OUTPUT_DIR will then be a subdirectory of generated_code in your project
DEV_OUTPUT_DIR = GENERATED_CODE_ROOT / "dev_outputs"

# Projects directory for organizing generated files by user request
PROJECTS_ROOT = GENERATED_CODE_ROOT / "projects"
CURRENT_PROJECT_DIR = PROJECTS_ROOT / "current"
ARCHIVED_PROJECTS_DIR = PROJECTS_ROOT / "archived"

# Add other configurations here, like model names
DEFAULT_MODEL_NAME = "gemini-2.5-flash"  # Used by PM, QA, Ops agents (15 RPM free tier)
PLANNER_MODEL_NAME = "gemini-2.5-flash"  # Used for planning tasks
DEV_MODEL_NAME = "gemini-2.5-pro"  # Used by Dev Agent only (higher quality code generation)

# GitHub Configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "")

# Render Configuration  
RENDER_API_KEY = os.getenv("RENDER_API_KEY", "")

# Database Configuration (Phase 2 - Production Enhancement)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/agenticai"
)